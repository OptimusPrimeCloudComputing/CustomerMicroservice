from __future__ import annotations
import base64
import json
import os
import logging
from typing import Dict

from flask import Request, make_response
from cloudevents.http import from_http

import sendgrid
from sendgrid.helpers.mail import Mail

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

"""
Cloud Function: gcf_send_email

This function is triggered by a Pub/Sub message published by the Customer microservice.
It expects the Pub/Sub message data to be a JSON object (base64 encoded by Pub/Sub) with
at least the following shape:

{
  "event_type": "CustomerCreated",            # optional (from attributes)
  "email": "student@school.edu",            # recipient email
  "name": "Student Name",                    # optional
  "subject": "Welcome!",                     # optional
  "body": "Hello ..."                        # optional
}

Authentication options (you must configure one in GCP):
- Service account impersonation + domain-wide delegation: provide SERVICE_ACCOUNT_KEY_B64
  (base64-encoded JSON key) and set GMAIL_IMPERSONATE to the user email to act as.
- OAuth2 refresh token (manual): provide OAUTH_REFRESH_TOKEN, OAUTH_CLIENT_ID and
  OAUTH_CLIENT_SECRET and the user email in GMAIL_IMPERSONATE. (Not implemented in code
  because it requires prior user consent flow to obtain refresh token.)

Environment variables used:
- SERVICE_ACCOUNT_KEY_B64: base64 of a service account JSON key that has
  the "https://www.googleapis.com/auth/gmail.send" scope via domain-wide delegation.
- GMAIL_IMPERSONATE: the email address to impersonate (the 'From' address).

Deployment: gcloud functions deploy gcf_send_email --runtime python312 --trigger-topic <topic>

"""



def send_email_sendgrid(to: str, subject: str, body: str, sender: str) -> dict:
    """Send an email using SendGrid API."""
    api_key = os.getenv("SENDGRID_API_KEY")
    if not api_key:
        raise RuntimeError("SENDGRID_API_KEY environment variable not set")
    sg = sendgrid.SendGridAPIClient(api_key)
    mail = Mail(
        from_email=sender,
        to_emails=to,
        subject=subject,
        plain_text_content=body
    )
    response = sg.send(mail)
    return {"status_code": response.status_code, "body": response.body, "headers": dict(response.headers)}


def create_message(sender: str, to: str, subject: str, body_text: str) -> Dict:
    """Create a base64url-encoded email object for Gmail API."""
    from email.message import EmailMessage

    msg = EmailMessage()
    msg.set_content(body_text)
    msg["To"] = to
    msg["From"] = sender
    msg["Subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}



def publish_send(to: str, subject: str, body: str) -> dict:
    sender = os.getenv("SENDGRID_SENDER_EMAIL", "noreply@example.com")
    return send_email_sendgrid(to, subject, body, sender)



# Cloud Functions 2nd Gen: HTTP trigger, CloudEvent (Eventarc Pub/Sub)
def gcf_send_email(request: Request):
    """
    HTTP entry point for Cloud Functions 2nd Gen (Eventarc Pub/Sub trigger).
    Expects a CloudEvent POSTed as JSON.
    """
    try:
        # Parse CloudEvent from HTTP request
        event = from_http(request.headers, request.get_data())
        # Pub/Sub message is in event.data["message"]["data"] (base64-encoded)
        message = event.data.get("message", {})
        data_b64 = message.get("data")
        if not data_b64:
            logger.error("No data in Pub/Sub message")
            return make_response(("No data in Pub/Sub message", 400))
        payload_raw = base64.b64decode(data_b64).decode("utf-8")
        logger.info("Decoded pubsub data: %s", payload_raw)
        payload = json.loads(payload_raw)
    except Exception:
        logger.exception("Failed to decode/parse pubsub message")
        return make_response(("Failed to decode/parse pubsub message", 400))

    to = payload.get("email")
    if not to:
        logger.error("No 'email' field in event payload; skipping")
        return make_response(("No 'email' field in event payload", 400))

    subject = payload.get("subject") or f"Notification: {payload.get('event_type','Update') }"
    name = payload.get("name") or "User"
    body = payload.get("body") or f"Hello {name},\n\nThis is an automated message from the Customer service.\n\nEvent: {payload.get('event_type') or 'update'}\n\nRegards\n"

    try:
        res = publish_send(to, subject, body)
        logger.info("Email sent via SendGrid: %s", res)
        return make_response(("Email sent", 200))
    except Exception:
        logger.exception("Failed to send email via SendGrid API")
        return make_response(("Failed to send email", 500))



if __name__ == "__main__":
    # local quick test helper
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True)
    parser.add_argument("--subject", default="Test")
    parser.add_argument("--body", default="Hello")
    parser.add_argument("--sender", default="noreply@example.com")
    args = parser.parse_args()
    print("This local runner will attempt to send email (requires SENDGRID_API_KEY and SENDGRID_SENDER_EMAIL set).")
    response = publish_send(args.to, args.subject, args.body)
    print(f"Status: {response['status_code']}")
    print(f"Body: {response['body']}")
