"""Policy + provider request/response schemas (M2)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

PolicyCategory = Literal[
    "vehicle", "machinery", "plant", "factory_property",
    "employees_group_health", "key_person",
    "stock_raw_material", "stock_finished_goods", "other",
]
PolicyStatus = Literal[
    "draft", "pending_approval", "active", "expiring", "lapsed", "renewed", "cancelled",
]


# ---- providers ----
class ProviderCreate(BaseModel):
    name: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None = None


class ProviderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None


# ---- policies ----
class PolicyCreate(BaseModel):
    org_id: uuid.UUID
    category: PolicyCategory
    title: str
    policy_number: str | None = None
    provider_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    sum_insured_inr: Decimal | None = None
    premium_inr: Decimal | None = None
    gst_inr: Decimal | None = None
    inception_date: date | None = None
    expiry_date: date | None = None
    renewal_date: date | None = None
    custom_fields: dict = {}


class PolicyUpdate(BaseModel):
    title: str | None = None
    policy_number: str | None = None
    provider_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    sum_insured_inr: Decimal | None = None
    premium_inr: Decimal | None = None
    gst_inr: Decimal | None = None
    inception_date: date | None = None
    expiry_date: date | None = None
    renewal_date: date | None = None
    status: PolicyStatus | None = None
    custom_fields: dict | None = None


class PolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    org_id: uuid.UUID
    category: str
    title: str
    policy_number: str | None
    provider_id: uuid.UUID | None
    owner_id: uuid.UUID | None
    sum_insured_inr: Decimal | None
    premium_inr: Decimal | None
    gst_inr: Decimal | None
    inception_date: date | None
    expiry_date: date | None
    renewal_date: date | None
    status: str
    prev_policy_id: uuid.UUID | None = None
    created_at: datetime


class RenewPolicyRequest(BaseModel):
    """Payload for POST /policies/{policy_id}/renew.

    Required: expiry_date for the new term.
    Optional fields override the carried-over source values; omitted fields fall
    back to the source policy values where applicable.
    """

    expiry_date: date
    renewal_date: date | None = None
    inception_date: date | None = None
    premium_inr: Decimal | None = None
    gst_inr: Decimal | None = None
    sum_insured_inr: Decimal | None = None
    policy_number: str | None = None
