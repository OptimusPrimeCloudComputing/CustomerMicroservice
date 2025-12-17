from __future__ import annotations

from typing import Optional, List
from uuid import UUID, uuid4
from datetime import date, datetime

from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Annotated

from .address import AddressBase

# Email must end with .edu
EduEmail = Annotated[
    str,
    StringConstraints(
        pattern=r"^[\w\.-]+@[\w\.-]+\.edu$",
        strip_whitespace=True,
    ),
]

UniversityIDType = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z]{2,4}\d{3,4}$"),  # e.g. UNI1234, cs4111
]


class CustomerBase(BaseModel):
    first_name: str = Field(
        ...,
        description="Given name.",
        json_schema_extra={"example": "Rahul"},
    )
    middle_name: Optional[str] = Field(
        None,
        description="Middle name.",
        json_schema_extra={"example": "Kumar"},
    )
    last_name: str = Field(
        ...,
        description="Family name.",
        json_schema_extra={"example": "Singh"},
    )

    university_id: Optional[UniversityIDType] = Field(
        None,
        description="University ID",
        json_schema_extra={"example": "UNI1234"},
    )

    email: EduEmail = Field(
        ...,
        description="Must be a valid .edu email address.",
        json_schema_extra={"example": "student@columbia.edu"},
    )
    phone: Optional[str] = Field(
        None,
        description="Contact phone number.",
        json_schema_extra={"example": "+1-234-567-8910"},
    )

    address: List[AddressBase] = Field(
        default_factory=list,
        description="List of mailing addresses of the customer.",
        json_schema_extra={
            "example": [
                {
                    "street": "123 Broadway Ave",
                    "city": "New York",
                    "state": "NY",
                    "postal_code": "10027",
                    "country": "USA",
                }
            ]
        },
    )

    birth_date: Optional[date] = Field(
        None,
        description="Date of birth (YYYY-MM-DD).",
        json_schema_extra={"example": "2000-07-15"},
    )

    status: str = Field(
        default="active",
        description="Customer status (active, inactive, pending).",
        json_schema_extra={"example": "active"},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "first_name": "Rahul",
                "middle_name": "Kumar",
                "last_name": "Singh",
                "university_id": "UNI1234",
                "email": "rahul@columbia.edu",
                "phone": "+1-234-567-8910",
                "birth_date": "2000-07-15",
                "status": "active",
                "address": [
                    {
                        "street": "123 Broadway Ave",
                        "city": "New York",
                        "state": "NY",
                        "postal_code": "10027",
                        "country": "USA",
                    }
                ],
            }
        }
    }


class CustomerCreate(CustomerBase):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "first_name": "Rahul",
                    "middle_name": "Kumar",
                    "last_name": "Singh",
                    "university_id": "UNI1234",
                    "email": "rahul@columbia.edu",
                    "phone": "+1-234-567-8910",
                    "birth_date": "2000-07-15",
                    "status": "active",
                    "address": [
                        {
                            "street": "123 Broadway Ave",
                            "city": "New York",
                            "state": "NY",
                            "postal_code": "10027",
                            "country": "USA",
                        }
                    ],
                }
            ]
        }
    }


class CustomerUpdate(BaseModel):
    """Partial update for a Customer; supply only fields to change."""
    first_name: Optional[str] = Field(
        None,
        description="Given name.",
        json_schema_extra={"example": "Rahul"},
    )
    middle_name: Optional[str] = Field(
        None,
        description="Middle name.",
        json_schema_extra={"example": "Kumar"},
    )
    last_name: Optional[str] = Field(
        None,
        description="Family name.",
        json_schema_extra={"example": "Singh"},
    )
    university_id: Optional[UniversityIDType] = Field(
        None,
        description="University ID.",
        json_schema_extra={"example": "UNI1234"},
    )
    email: Optional[EduEmail] = Field(
        None,
        description=".edu email.",
        json_schema_extra={"example": "rahul@columbia.edu"},
    )
    phone: Optional[str] = Field(
        None,
        description="Contact phone.",
        json_schema_extra={"example": "+1-234-567-8910"},
    )
    address: Optional[List[AddressBase]] = Field(
        None,
        description="List of mailing addresses.",
    )
    birth_date: Optional[date] = Field(
        None,
        description="DOB (YYYY-MM-DD).",
        json_schema_extra={"example": "2000-07-15"},
    )
    status: Optional[str] = Field(
        None,
        description="Customer status.",
        json_schema_extra={"example": "inactive"},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "first_name": "Rahul",
                "middle_name": "K.",
                "last_name": "Singh",
                "email": "rahul@columbia.edu",
                "status": "inactive",
            }
        }
    }


class CustomerRead(CustomerBase):
    """Server representation returned to clients (composite view)."""
    customer_id: UUID = Field(
        default_factory=uuid4,
        description="Composite-level Customer ID.",
        json_schema_extra={"example": "99999999-9999-4999-8999-999999999999"},
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp (UTC).",
        json_schema_extra={"example": "2025-09-30T10:20:30Z"},
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp (UTC).",
        json_schema_extra={"example": "2025-09-30T12:00:00Z"},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "customer_id": "99999999-9999-4999-8999-999999999999",
                    "first_name": "Rahul",
                    "middle_name": "Kumar",
                    "last_name": "Singh",
                    "university_id": "UNI1234",
                    "email": "rahul@columbia.edu",
                    "phone": "+1-234-567-8910",
                    "birth_date": "2000-07-15",
                    "status": "active",
                    "address": [
                        {
                            "street": "123 Broadway Ave",
                            "city": "New York",
                            "state": "NY",
                            "postal_code": "10027",
                            "country": "USA",
                        }
                    ],
                    "created_at": "2025-09-30T10:20:30Z",
                    "updated_at": "2025-09-30T12:00:00Z",
                }
            ]
        }
    }
