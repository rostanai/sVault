"""Tenancy + org hierarchy + profiles + invitations (mirrors 0002_platform_tenancy.sql)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import UUIDPK, Base, Timestamps

# Enum types are created by the SQL migrations — do NOT let SQLAlchemy create them.
org_type_enum = ENUM("parent", "subsidiary", name="org_type", create_type=False)
tenant_role_enum = ENUM(
    "admin", "manager", "owner", "viewer", name="tenant_role", create_type=False
)


class Tenant(Base, UUIDPK, Timestamps):
    """A corporate group (the tenant)."""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active")

    organizations: Mapped[list[Organization]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class Organization(Base, UUIDPK, Timestamps):
    """A company within the group — parent or subsidiary (self-referential tree)."""

    __tablename__ = "organizations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    parent_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    org_type: Mapped[str] = mapped_column(org_type_enum, default="parent")
    gstin: Mapped[str | None] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tenant: Mapped[Tenant] = relationship(back_populates="organizations")
    children: Mapped[list[Organization]] = relationship(
        back_populates="parent", remote_side="Organization.parent_org_id"
    )
    parent: Mapped[Organization | None] = relationship(
        back_populates="children", remote_side="Organization.id"
    )


class Profile(Base, Timestamps):
    """App user — 1:1 with auth.users; carries tenant/org/role."""

    __tablename__ = "profiles"

    # PK == auth.users.id
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL")
    )
    role: Mapped[str] = mapped_column(tenant_role_enum, default="viewer")
    full_name: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String)  # E.164 for WhatsApp/SMS
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Invitation(Base, UUIDPK):
    """Team invite — email link that auto-joins the correct tenant/org."""

    __tablename__ = "invitations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL")
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(tenant_role_enum, default="viewer")
    token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id")
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
