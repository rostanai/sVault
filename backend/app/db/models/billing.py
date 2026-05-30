"""Billing ORM models (M5): Plan, Subscription, Invoice, BillingEvent, PlatformSetting,
PlatformAuditLog.

Mirrors 0002_platform_tenancy.sql (plans, platform_settings, platform_audit_log) and
0003_billing.sql (subscriptions, invoices, billing_events).
The DB owns DDL (enums/triggers/RLS); ENUM(create_type=False) throughout.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDPK, Base, Timestamps

# ---- shared enum types (all pre-created by migrations) ----
plan_tier_enum = ENUM(
    "free", "starter", "professional", "enterprise",
    name="plan_tier", create_type=False,
)

subscription_status_enum = ENUM(
    "trialing", "active", "past_due", "paused", "cancelled", "expired",
    name="subscription_status", create_type=False,
)

audit_action_enum = ENUM(
    "create", "update", "delete", "login", "logout",
    "approve", "reject", "export", "impersonate",
    name="audit_action", create_type=False,
)


# ---------------------------------------------------------------------------
# Platform plane
# ---------------------------------------------------------------------------

class Plan(Base, UUIDPK, Timestamps):
    """Subscription plan definition — managed by Super Admin; read by tenants."""

    __tablename__ = "plans"

    tier: Mapped[str] = mapped_column(plan_tier_enum, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    billing_period: Mapped[str] = mapped_column(String, default="monthly")  # monthly | annual
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # {"features": {"rag": true, "sms": false, "api": false},
    #  "limits": {"policies": 100, "users": 3, "alerts_month": 500}}
    entitlements: Mapped[dict] = mapped_column(JSONB, default=dict)
    razorpay_plan_id: Mapped[str | None] = mapped_column(Text)


class PlatformSetting(Base):
    """Global config & secrets (AI keys, channel creds). Value always encrypted."""

    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value_encrypted: Mapped[str | None] = mapped_column(Text)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )


# ---------------------------------------------------------------------------
# Tenant plane
# ---------------------------------------------------------------------------

class Subscription(Base, UUIDPK, Timestamps):
    """One subscription per tenant (group-level billing by default — DECISIONS A7/D10)."""

    __tablename__ = "subscriptions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id")
    )
    status: Mapped[str] = mapped_column(subscription_status_enum, default="trialing")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    razorpay_customer_id: Mapped[str | None] = mapped_column(Text)
    razorpay_subscription_id: Mapped[str | None] = mapped_column(Text)


class Invoice(Base, UUIDPK):
    """Invoice / payment record — mirrors Razorpay; GST-aware."""

    __tablename__ = "invoices"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL")
    )
    amount_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gst_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, default="created")  # created|paid|failed|refunded
    razorpay_invoice_id: Mapped[str | None] = mapped_column(Text)
    razorpay_payment_id: Mapped[str | None] = mapped_column(Text)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pdf_url: Mapped[str | None] = mapped_column(Text)


class BillingEvent(Base, UUIDPK):
    """Razorpay webhook events — idempotency guard via unique event_id."""

    __tablename__ = "billing_events"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    event_id: Mapped[str | None] = mapped_column(Text, unique=True)  # Razorpay event id
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )


class PlatformAuditLog(Base):
    """Platform-plane audit log — DPDP 1-yr retention (mirrors platform_audit_log table).

    Written by platform_service for every Super Admin mutation:
    plan create/update, tenant suspend/activate, setting create/update/rotate.
    actor is the super-admin auth.users id; target is the object id / key (never a secret
    value); detail is a small jsonb with context (field names changed, not values).
    """

    __tablename__ = "platform_audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(audit_action_enum, nullable=False)
    target: Mapped[str | None] = mapped_column(Text)  # e.g. plan_id, tenant_id, setting key
    detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )
