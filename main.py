from __future__ import annotations
from google.cloud import pubsub_v1
import json

import os
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, UTC
from typing import List, Dict
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import base64

from sqlalchemy.orm import composite
from starlette.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from models.address import AddressBase, AddressRead, AddressCreate, AddressUpdate
from models.customer import CustomerRead, CustomerCreate, CustomerUpdate
from models.health import Health
from middleware.auth import get_current_user
from utils.jwt_utils import create_access_token
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "cloud-computing-478817")
PUBSUB_TOPIC = os.getenv("PUBSUB_TOPIC_CUSTOMER_EVENTS", "customerTopic")

if PROJECT_ID and PUBSUB_TOPIC:
    publisher: pubsub_v1.PublisherClient | None = pubsub_v1.PublisherClient()
    TOPIC_PATH: str | None = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC)
    logger.info(
        "Pub/Sub enabled for composite: project=%s topic=%s",
        PROJECT_ID,
        PUBSUB_TOPIC,
    )
else:
    publisher = None
    TOPIC_PATH = None
    logger.warning(
        "Pub/Sub DISABLED for composite: GCP_PROJECT_ID or PUBSUB_TOPIC_CUSTOMER_EVENTS not set"
    )

port = int(os.environ.get("FASTAPIPORT", 8002))

CUSTOMER_SERVICE_URL = os.environ.get(
    "CUSTOMER_SERVICE_URL", "https://customer-atomic-service-453095374298.europe-west1.run.app")
ADDRESS_SERVICE_URL = os.environ.get(
    "ADDRESS_SERVICE_URL", "https://customer-address-atomic-service-453095374298.europe-west1.run.app")

executor = ThreadPoolExecutor(max_workers=4)

app = FastAPI(
    title="Customer Composite API",
    description="Composite microservice for customers and their addresses.",
    version="0.0.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GoogleAuthRequest(BaseModel):
    credential: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "credential": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }
    }


@app.post("/auth/google")
async def auth_google(body: GoogleAuthRequest):
    """Exchange Google ID token for app JWT.

    Expects body: {"credential": "<google_id_token>"}
    For this assignment, we trust the frontend to send a valid token
    and extract basic profile claims from it.
    """
    credential = body.credential
    if not credential:
        raise HTTPException(status_code=400, detail="Missing credential")

    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not google_client_id:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_CLIENT_ID not configured on server",
        )

    try:
        idinfo = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            google_client_id,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google ID token")

    email = idinfo.get("email")
    name = idinfo.get("name") or "Google User"
    picture = idinfo.get("picture")
    sub = idinfo.get("sub")

    # Optional: enforce .edu emails for this app
    if not email or not email.endswith(".edu"):
        raise HTTPException(
            status_code=403, detail="Email must be a .edu address")

    jwt_payload = {
        "sub": sub,
        "email": email,
        "name": name,
    }
    app_token = create_access_token(jwt_payload)

    return {
        "token": app_token,
        "user": {
            "id": sub,
            "email": email,
            "name": name,
            "picture": picture,
        },
    }

# PUB/SUB GCP


@app.post("/pubsub/push")
async def pubsub_push(request: Request):
    envelope = await request.json()

    if "message" not in envelope:
        return {"status": "invalid pubsub message"}

    message = envelope["message"]
    data = message.get("data")

    if data:
        decoded = base64.b64decode(data).decode("utf-8")
        print("Received pubsub message:", decoded)

    return {"status": "ok"}

# Pub/Sub helper


def publish_event(event_type: str, payload: dict) -> None:
    if not publisher or not TOPIC_PATH:
        logger.info(
            "Pub/Sub disabled; skipping publish for event_type=%s", event_type
        )
        return

    try:
        data = json.dumps(payload, default=str).encode("utf-8")
        attributes = {
            "event_type": event_type,
        }
        uni = payload.get("university_id")
        if uni:
            attributes["university_id"] = str(uni)

        future = publisher.publish(
            TOPIC_PATH,
            data=data,
            **attributes,
        )

        def _on_done(f):
            try:
                msg_id = f.result()
                logger.info(
                    "Published Pub/Sub event_type=%s message_id=%s",
                    event_type,
                    msg_id,
                )
            except Exception:
                logger.exception(
                    "Pub/Sub publish callback failed for event_type=%s", event_type
                )

        future.add_done_callback(_on_done)

    except Exception:
        logger.exception("Failed to publish Pub/Sub event_type=%s", event_type)


def make_health() -> Health:
    return Health(
        status=200,
        status_message="OK",
        timestamp=datetime.now(UTC).isoformat() + "Z",
        ip_address=socket.gethostbyname(socket.gethostname()),
    )


@app.get("/health", response_model=Health)
def get_health():
    return make_health()


def fetch_customer_atomic(university_id: str) -> Dict:
    try:
        print(CUSTOMER_SERVICE_URL)
        resp = httpx.get(
            f"{CUSTOMER_SERVICE_URL}/customers/{university_id}",
            timeout=15.0,
        )
    except httpx.RequestError as exc:
        print(f"Customer service request failed: {exc!r}")
        logger.exception("Customer service request failed.")
        raise HTTPException(
            status_code=502, detail=f"Customer service unavailable: {exc}")

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Customer not found")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    return resp.json()


def fetch_addresses_atomic(university_id: str) -> List[Dict]:
    try:
        resp = httpx.get(
            f"{ADDRESS_SERVICE_URL}/customers/{university_id}/addresses",
            timeout=15.0,
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502, detail="Address service unavailable")

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    return resp.json()


# COMPOSITE: Customer endpoints
@app.post("/customers", response_model=CustomerRead, status_code=201)
def create_customer(customer: CustomerCreate):
    """
    Composite create:
    - Create customer in Customer Atomic (without addresses).
    - Then create associated addresses in Address Atomic.
    - Return aggregated CustomerRead (customer + address list).
    """
    if customer.university_id is None:
        raise HTTPException(
            status_code=400,
            detail="university_id is required to create a customer.",
        )

    payload = customer.model_dump(mode='json')
    address_list = payload.pop("address", [])
    customer_payload = payload

    # 1) Create the customer in the Customer Atomic service
    print(f"{CUSTOMER_SERVICE_URL}/customers")
    try:
        resp = httpx.post(
            f"{CUSTOMER_SERVICE_URL}/customers",
            json=customer_payload,
            timeout=15.0,
        )

    except httpx.RequestError as exc:
        print(f"Customer service request failed: {exc!r}")
        logger.exception("Customer service request failed.")
        raise HTTPException(
            status_code=502, detail=f"Customer service unavailable: {exc}")

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    customer_data = resp.json()
    uni_id = customer_data["university_id"]

    # 2) Create addresses in Address Atomic
    created_addresses: List[AddressBase] = []
    for addr in address_list:
        addr_payload = {
            "university_id": uni_id,
            **addr,
        }
        try:
            addr_resp = httpx.post(
                f"{ADDRESS_SERVICE_URL}/addresses",
                json=addr_payload,
                timeout=15.0,
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=502, detail="Address service unavailable")

        if addr_resp.status_code >= 400:
            raise HTTPException(
                status_code=addr_resp.status_code, detail=addr_resp.text)

        addr_data = addr_resp.json()
        created_addresses.append(
            AddressBase(
                street=addr_data["street"],
                city=addr_data["city"],
                state=addr_data["state"],
                postal_code=addr_data["postal_code"],
                country=addr_data["country"],
            )
        )

    # 3) Build composite CustomerRead
    base_fields = {
        k: v
        for k, v in customer_data.items()
        if k not in ("customer_id", "address")
    }

    composite_customer = CustomerRead(
        customer_id=uuid4(),
        address=created_addresses,
        **base_fields,
    )

    try:
        publish_event(
            "CustomerCreated",
            composite_customer.model_dump(mode="json"),
        )
    except Exception:
        logger.exception("Error while publishing CustomerCreated event")

    return composite_customer


@app.get("/customers/{university_id}", response_model=CustomerRead)
def get_customer(university_id: str, current_user: dict = Depends(get_current_user)):
    """
    Composite read:

    USES THREADS:
    - In parallel, fetch:
        * Customer from Customer Atomic
        * Addresses from Address Atomic
    - Aggregate into a single CustomerRead object.
    """
    future_customer = executor.submit(fetch_customer_atomic, university_id)
    future_addresses = executor.submit(fetch_addresses_atomic, university_id)

    customer_data = future_customer.result()
    addresses_data = future_addresses.result()

    address_objs = [
        AddressBase(
            street=a["street"],
            city=a["city"],
            state=a["state"],
            postal_code=a["postal_code"],
            country=a["country"],
        )
        for a in addresses_data
    ]

    base_fields = {
        k: v
        for k, v in customer_data.items()
        if k not in ("customer_id", "address")
    }

    return CustomerRead(
        customer_id=uuid4(),
        address=address_objs,
        **base_fields,
    )


@app.patch("/customers/{university_id}", response_model=CustomerRead)
def update_customer(university_id: str, update: CustomerUpdate):
    """
    Composite update:

    - PATCH core customer fields in Customer Atomic.
    - Addresses are managed using separate endpoints.
    - Then call composite GET to return the updated aggregated view.
    """
    update_data = update.model_dump(mode='json', exclude_unset=True)
    update_data.pop("address", None)

    try:
        resp = httpx.patch(
            f"{CUSTOMER_SERVICE_URL}/customers/{university_id}",
            json=update_data,
            timeout=15.0,
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502, detail="Customer service unavailable")

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Customer not found")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    composite_updated = get_customer(university_id)
    try:
        publish_event(
            "CustomerUpdated",
            composite_updated.model_dump(mode="json"),
        )
    except Exception:
        logger.exception("Error while publishing CustomerUpdated event")

    return composite_updated



@app.delete("/customers/{university_id}", status_code=204)
def delete_customer(university_id: str):
    """
    Composite delete:

    - Delete all addresses for this customer in Address Atomic.
    - Delete the customer in Customer Atomic.
    """
    try:
        addr_resp = httpx.delete(
            f"{ADDRESS_SERVICE_URL}/customers/{university_id}/addresses",
            timeout=15.0,
        )
    except httpx.RequestError as exc:
        logger.exception("Address service request failed: %s", exc)
        raise HTTPException(
            status_code=502, detail="Address service unavailable")

    if addr_resp.status_code not in (200, 204, 404):
        raise HTTPException(
            status_code=addr_resp.status_code, detail=addr_resp.text)

    try:
        cust_resp = httpx.delete(
            f"{CUSTOMER_SERVICE_URL}/customers/{university_id}",
            timeout=15.0,
        )
    except httpx.RequestError as exc:
        logger.exception("Customer service request failed: %s", exc)
        raise HTTPException(
            status_code=502, detail="Customer service unavailable")

    if cust_resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Customer not found")
    if cust_resp.status_code >= 400:
        raise HTTPException(
            status_code=cust_resp.status_code, detail=cust_resp.text)

    try:
        publish_event(
            "CustomerDeleted",
            {
                "university_id": university_id,
                "deleted_at": datetime.now(UTC).isoformat() + "Z",
            },
        )
    except Exception:
        logger.exception("Error while publishing CustomerDeleted event")

    return JSONResponse(status_code=204, content=None)


# ---------------------------------------------------------------------------
# COMPOSITE: Address endpoints (with logical FK check)
# ---------------------------------------------------------------------------

@app.post(
    "/customers/{university_id}/addresses",
    response_model=AddressRead,
    status_code=201,
)
def create_address_for_customer(university_id: str, address: AddressCreate):
    """
    Composite create-address:
    - ENFORCES LOGICAL FOREIGN KEY:
        First verifies that the customer with this university_id exists
        by calling Customer Atomic.
    - Then creates the address in Address Atomic.
    """
    # FK check: will raise HTTPException(404) if not found
    fetch_customer_atomic(university_id)

    # Ensure body university_id (if present) is consistent
    addr_payload = address.model_dump(mode='json')
    body_uni = addr_payload.get("university_id")
    if body_uni is not None and body_uni != university_id:
        raise HTTPException(
            status_code=400,
            detail="university_id in path and body must match.",
        )

    # Force correct FK
    addr_payload["university_id"] = university_id

    try:
        resp = httpx.post(
            f"{ADDRESS_SERVICE_URL}/addresses",
            json=addr_payload,
            timeout=15.0,
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502, detail="Address service unavailable")

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    return AddressRead(**resp.json())


@app.get(
    "/customers/{university_id}/addresses",
    response_model=List[AddressRead],
)
def list_customer_addresses(university_id: str):
    """
    Composite list-addresses:
    """
    addresses_data = fetch_addresses_atomic(university_id)
    return [AddressRead(**a) for a in addresses_data]


@app.patch(
    "/customers/{university_id}/addresses/{address_id}",
    response_model=AddressRead,
)
def update_address_for_customer(
    university_id: str,
    address_id: str,
    update: AddressUpdate,
):
    """
    Composite update-address:

    - Delegates to Address Atomic PATCH /customers/{university_id}/addresses/{address_id}
    - Atomic service ensures the (university_id, address_id) relationship is valid.
    """
    update_data = update.model_dump(mode='json', exclude_unset=True)

    try:
        resp = httpx.patch(
            f"{ADDRESS_SERVICE_URL}/customers/{university_id}/addresses/{address_id}",
            json=update_data,
            timeout=15.0,
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502, detail="Address service unavailable")

    if resp.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Address not found for this university_id",
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    return AddressRead(**resp.json())


@app.delete(
    "/customers/{university_id}/addresses/{address_id}",
    status_code=204,
)
def delete_address_for_customer(university_id: str, address_id: str):
    """
    Composite delete-address:

    - Delegates to Address Atomic DELETE /customers/{university_id}/addresses/{address_id}
    """
    try:
        resp = httpx.delete(
            f"{ADDRESS_SERVICE_URL}/customers/{university_id}/addresses/{address_id}",
            timeout=15.0,
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502, detail="Address service unavailable")

    if resp.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Address not found for this university_id",
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    return JSONResponse(status_code=204, content=None)


# -----
# Root
# -----

@app.get("/")
def root():
    return {
        "message": "Customer Composite Service. See /docs for OpenAPI UI.",
        "atomic_services": {
            "customer": CUSTOMER_SERVICE_URL,
            "address": ADDRESS_SERVICE_URL,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
