"""Approval workflow ORM model (mirrors 0005_alerts_approvals_audit_rag.sql).

Enums are created by migration; use create_type=False so SQLAlchemy does not
try to CREATE TYPE on every engine init.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDPK, Base

approval_action_enum = ENUM(
    "renewal",
    "new_policy",
    "vendor_finalization",
    "high_value_premium",
    "other",
    name="approval_action",
    create_type=False,
)
approval_status_enum = ENUM(
    "pending",
    "approved",
    "rejected",
    "cancelled",
    name="approval_status",
    create_type=False,
)


class Approval(Base, UUIDPK):
    __tablename__ = "approvals"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE")
    )
    action_type: Mapped[str] = mapped_column(approval_action_enum, nullable=False)
    entity_type: Mapped[str] = mapped_column(nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    amount_inr: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(approval_status_enum, nullable=False, default="pending")
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id")
    )
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id")
    )
    is_self_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
