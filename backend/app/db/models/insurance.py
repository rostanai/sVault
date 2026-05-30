"""Insurance domain models: providers, policies, documents (mirrors 0004_insurance.sql)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDPK, Base, Timestamps

policy_category_enum = ENUM(
    "vehicle", "machinery", "plant", "factory_property",
    "employees_group_health", "key_person",
    "stock_raw_material", "stock_finished_goods", "other",
    name="policy_category", create_type=False,
)
policy_status_enum = ENUM(
    "draft", "pending_approval", "active", "expiring", "lapsed", "renewed", "cancelled",
    name="policy_status", create_type=False,
)
document_type_enum = ENUM(
    "policy", "schedule", "endorsement", "invoice", "claim", "other",
    name="document_type", create_type=False,
)


class Provider(Base, UUIDPK, Timestamps):
    __tablename__ = "providers"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String)
    contact_email: Mapped[str | None] = mapped_column(String)
    contact_phone: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)


class Policy(Base, UUIDPK, Timestamps):
    __tablename__ = "policies"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(policy_category_enum, nullable=False)
    policy_number: Mapped[str | None] = mapped_column(String)
    title: Mapped[str] = mapped_column(String, nullable=False)  # asset / description
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers.id", ondelete="SET NULL")
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL")
    )
    sum_insured_inr: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    premium_inr: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    gst_inr: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=0)
    inception_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    renewal_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(policy_status_enum, default="active")
    prev_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id", ondelete="SET NULL")
    )
    custom_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id")
    )


class PolicyDocument(Base, UUIDPK):
    __tablename__ = "policy_documents"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )
    doc_type: Mapped[str] = mapped_column(document_type_enum, default="policy")
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String)
    size_bytes: Mapped[int | None] = mapped_column()
    version: Mapped[int] = mapped_column(default=1)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
