"""Request/response schemas for M1 (auth/onboarding, orgs, invitations)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

TenantRole = Literal["admin", "manager", "owner", "viewer"]


# ---- onboarding / me ----
class OnboardRequest(BaseModel):
    company_name: str
    full_name: str | None = None


class OnboardResponse(BaseModel):
    tenant_id: uuid.UUID
    org_id: uuid.UUID
    role: str = "admin"
    trial_ends_at: datetime
    note: str = "Refresh your session to load the new tenant claims."


class MeResponse(BaseModel):
    user_id: str
    tenant_id: str | None
    org_id: str | None
    role: str
    is_super_admin: bool
    email: str | None


# ---- organizations ----
class OrgCreate(BaseModel):
    name: str
    parent_org_id: uuid.UUID | None = None
    org_type: Literal["parent", "subsidiary"] = "subsidiary"
    gstin: str | None = None


class OrgRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    parent_org_id: uuid.UUID | None
    name: str
    org_type: str
    gstin: str | None
    is_active: bool


# ---- invitations ----
class InvitationCreate(BaseModel):
    email: str
    role: TenantRole = "viewer"
    org_id: uuid.UUID | None = None


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    role: str
    org_id: uuid.UUID | None
    expires_at: datetime


class AcceptInvite(BaseModel):
    token: str
