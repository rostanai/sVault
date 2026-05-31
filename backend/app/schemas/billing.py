"""Billing + platform request/response schemas (M5)."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tier: str
    name: str
    description: str | None
    price_inr: Decimal
    billing_period: str
    is_active: bool
    entitlements: dict
    razorpay_plan_id: str | None
    created_at: datetime
    updated_at: datetime


class PlanCreate(BaseModel):
    tier: str
    name: str
    description: str | None = None
    price_inr: Decimal = Decimal("0")
    billing_period: str = "monthly"
    is_active: bool = True
    entitlements: dict = {}
    razorpay_plan_id: str | None = None


class PlanUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price_inr: Decimal | None = None
    billing_period: str | None = None
    is_active: bool | None = None
    entitlements: dict | None = None
    razorpay_plan_id: str | None = None


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    plan_id: uuid.UUID | None
    status: str
    trial_ends_at: datetime | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    razorpay_subscription_id: str | None
    created_at: datetime
    updated_at: datetime


class SubscriptionWithEntitlements(BaseModel):
    """Subscription + resolved entitlements for the in-app subscription page."""
    subscription: SubscriptionRead | None
    entitlements: dict


class SubscribeRequest(BaseModel):
    plan_id: uuid.UUID
    notes: dict | None = None


class SubscribeResponse(BaseModel):
    subscription_id: str
    status: str
    plan_id: str
    razorpay_subscription_id: str | None = None
    short_url: str | None = None
    payment_required: bool = False
    """True when a real Razorpay checkout is needed (branch 1: live keys + razorpay_plan_id set).
    False when the upgrade was immediately activated in simulated/demo mode (branch 2: no live
    Razorpay configured or plan has no razorpay_plan_id).  The frontend should open the checkout
    flow only when this is True; otherwise it should simply refresh the subscription state."""


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount_inr: Decimal
    gst_inr: Decimal
    status: str
    issued_at: datetime
    paid_at: datetime | None
    pdf_url: str | None
    razorpay_invoice_id: str | None


# ---------------------------------------------------------------------------
# Platform settings
# ---------------------------------------------------------------------------

class SettingRead(BaseModel):
    key: str
    value: str | None  # always masked for secrets
    is_secret: bool
    updated_at: datetime | None


class SettingWrite(BaseModel):
    value: str
    is_secret: bool = True


# ---------------------------------------------------------------------------
# Tenants (platform view)
# ---------------------------------------------------------------------------

class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Platform analytics
# ---------------------------------------------------------------------------

class TenantCounts(BaseModel):
    """Breakdown of tenant counts by status."""

    total: int
    active: int
    suspended: int


class TierCount(BaseModel):
    """Count of active subscriptions per plan tier."""

    tier: str
    count: int


class PlatformAnalytics(BaseModel):
    """Platform-wide metrics for the Super Admin overview dashboard."""

    tenants: TenantCounts
    subscriptions: dict[str, int]
    by_tier: list[TierCount]
    mrr_inr: str  # sum of price_inr over active subscriptions, as a numeric string
