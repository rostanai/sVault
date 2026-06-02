"""Provider service — get/update + contact-log CRUD (tenant-scoped).

Defense in depth: tenant isolation is enforced here AND by RLS in the DB.
Cross-tenant / non-owned access raises not_found (never reveals existence).
See docs/ERROR_HANDLING.md.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import not_found
from app.core.security import CurrentUser
from app.db.models.insurance import Provider
from app.db.models.provider_contacts import ProviderContact
from app.schemas.provider_contact import ProviderContactCreate, ProviderUpdate

# ---------------------------------------------------------------------------
# Provider helpers
# ---------------------------------------------------------------------------

async def find_or_create_by_name(
    db: AsyncSession, user: CurrentUser, name: str
) -> Provider | None:
    """Return the tenant's provider with this name (case-insensitive), creating it
    if absent. Used by AI intake to auto-register the insurer. Returns None for a
    blank name. The row is flushed (id populated) but NOT committed — the caller's
    transaction (e.g. create_policy) commits provider + policy atomically.
    """
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    stmt = select(Provider).where(
        Provider.tenant_id == uuid.UUID(user.tenant_id),
        func.lower(Provider.name) == cleaned.lower(),
    )
    provider = (await db.execute(stmt)).scalar_one_or_none()
    if provider is None:
        provider = Provider(tenant_id=uuid.UUID(user.tenant_id), name=cleaned)
        db.add(provider)
        await db.flush()
    return provider


async def get_provider(
    db: AsyncSession, user: CurrentUser, provider_id: uuid.UUID
) -> Provider:
    """Load a provider belonging to the user's tenant; raise 404 otherwise."""
    stmt = select(Provider).where(
        Provider.id == provider_id,
        Provider.tenant_id == uuid.UUID(user.tenant_id),
    )
    provider = (await db.execute(stmt)).scalar_one_or_none()
    if provider is None:
        raise not_found("Provider not found")
    return provider


async def update_provider(
    db: AsyncSession,
    user: CurrentUser,
    provider_id: uuid.UUID,
    payload: ProviderUpdate,
) -> Provider:
    """Apply non-null PATCH fields to a provider; commit and return updated row."""
    provider = await get_provider(db, user, provider_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(provider, field, value)
    await db.commit()
    await db.refresh(provider)
    return provider


# ---------------------------------------------------------------------------
# Contact log helpers
# ---------------------------------------------------------------------------

async def _get_provider_scoped(
    db: AsyncSession, user: CurrentUser, provider_id: uuid.UUID
) -> Provider:
    """Internal guard: confirm provider belongs to tenant before touching contacts."""
    return await get_provider(db, user, provider_id)


async def list_contacts(
    db: AsyncSession,
    user: CurrentUser,
    provider_id: uuid.UUID,
) -> list[ProviderContact]:
    """Return all contact-log entries for a provider, newest contacted_at first."""
    await _get_provider_scoped(db, user, provider_id)  # 404 if provider not in tenant
    stmt = (
        select(ProviderContact)
        .where(
            ProviderContact.provider_id == provider_id,
            ProviderContact.tenant_id == uuid.UUID(user.tenant_id),
        )
        .order_by(ProviderContact.contacted_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def create_contact(
    db: AsyncSession,
    user: CurrentUser,
    provider_id: uuid.UUID,
    payload: ProviderContactCreate,
) -> ProviderContact:
    """Log a new provider interaction; contacted_at defaults to UTC now when omitted."""
    await _get_provider_scoped(db, user, provider_id)  # 404 if provider not in tenant
    contact = ProviderContact(
        tenant_id=uuid.UUID(user.tenant_id),
        provider_id=provider_id,
        kind=payload.kind,
        subject=payload.subject,
        note=payload.note,
        contacted_at=payload.contacted_at or datetime.now(UTC),
        created_by=uuid.UUID(user.user_id),
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


async def delete_contact(
    db: AsyncSession,
    user: CurrentUser,
    contact_id: uuid.UUID,
) -> None:
    """Delete a contact-log entry (tenant-scoped); raise 404 if not found."""
    stmt = select(ProviderContact).where(
        ProviderContact.id == contact_id,
        ProviderContact.tenant_id == uuid.UUID(user.tenant_id),
    )
    contact = (await db.execute(stmt)).scalar_one_or_none()
    if contact is None:
        raise not_found("Contact not found")
    await db.delete(contact)
    await db.commit()
