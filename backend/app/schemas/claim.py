"""Claims request/response schemas — Pydantic v2.

Separate Create / Update / Read shapes.  ORM objects are never returned directly.
ClaimStatus is a Literal to avoid a PG enum dependency in the schema layer.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ClaimStatus = Literal[
    "draft",
    "reported",
    "under_review",
    "approved",
    "rejected",
    "settled",
    "closed",
]


class ClaimCreate(BaseModel):
    """Payload to open a new claim against a policy."""

    policy_id: uuid.UUID = Field(..., description="The policy this claim is filed against")
    claim_number: str | None = Field(
        None, max_length=100, description="Insurer-assigned claim reference number"
    )
    status: ClaimStatus = Field(
        "reported",
        description=(
            "Initial status; defaults to 'reported'. "
            "Pass 'draft' to save without submitting."
        ),
    )
    claim_amount_inr: Annotated[
        Decimal | None, Field(None, gt=0, description="Claimed amount in INR")
    ] = None
    incident_date: date | None = Field(
        None, description="Date the insured incident occurred"
    )
    description: str | None = Field(
        None, max_length=5000, description="Description of the incident / claim"
    )


class ClaimUpdate(BaseModel):
    """Partial update for a claim.  All fields are optional.

    ``note`` is an optional free-text string recorded as a ClaimEvent alongside any
    status change; it is NOT stored as a column on the claims table.
    """

    status: ClaimStatus | None = None
    claim_number: str | None = Field(None, max_length=100)
    claim_amount_inr: Annotated[Decimal | None, Field(None, gt=0)] = None
    approved_amount_inr: Annotated[Decimal | None, Field(None, ge=0)] = None
    incident_date: date | None = None
    description: str | None = Field(None, max_length=5000)
    note: str | None = Field(
        None,
        max_length=2000,
        description="Optional note recorded as a claim event alongside any status change",
    )


class ClaimRead(BaseModel):
    """Full claim record returned by all endpoints.

    ``policy_title`` is enriched by the service layer (joined from policies).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    policy_id: uuid.UUID
    org_id: uuid.UUID
    claim_number: str | None
    status: str
    claim_amount_inr: Decimal | None
    approved_amount_inr: Decimal | None
    incident_date: date | None
    reported_date: date | None
    description: str | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    policy_title: str | None = None


class ClaimEventRead(BaseModel):
    """A single audit event on a claim (status_change or free-text note)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    claim_id: uuid.UUID
    event_type: str
    from_status: str | None
    to_status: str | None
    note: str | None
    created_by: uuid.UUID | None
    created_at: datetime
