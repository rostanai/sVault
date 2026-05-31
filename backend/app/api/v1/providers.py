"""Provider (insurer/vendor) endpoints (M2).

Routes
------
GET  /providers                    — list all providers for tenant
POST /providers                    — create a provider          [provider:manage]
GET  /providers/{id}               — get provider detail        [any authenticated]
PATCH /providers/{id}              — update provider fields     [provider:manage]
GET  /providers/{id}/contacts      — list contact log           [any authenticated]
POST /providers/{id}/contacts      — log a contact interaction  [provider:manage]
DELETE /provider-contacts/{id}     — delete a contact entry     [provider:manage]
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import get_current_user, require_permission
from app.core.security import CurrentUser
from app.db.models import Provider
from app.db.session import get_db
from app.schemas.policy import ProviderCreate, ProviderRead
from app.schemas.provider_contact import (
    ProviderContactCreate,
    ProviderContactRead,
    ProviderUpdate,
)
from app.services import provider_service

router = APIRouter(prefix="/providers", tags=["providers"])

_manage = require_permission("provider:manage")


# ---------------------------------------------------------------------------
# Existing routes (list + create)
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ProviderRead])
async def list_providers(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProviderRead]:
    """List all insurance providers belonging to the caller's tenant."""
    stmt = select(Provider).where(Provider.tenant_id == uuid.UUID(user.tenant_id))
    return list((await db.execute(stmt)).scalars().all())


@router.post("", response_model=ProviderRead, status_code=201)
async def create_provider(
    payload: ProviderCreate,
    user: CurrentUser = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> ProviderRead:
    """Create a new insurance provider (requires provider:manage)."""
    provider = Provider(tenant_id=uuid.UUID(user.tenant_id), **payload.model_dump())
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


# ---------------------------------------------------------------------------
# Provider detail + update
# ---------------------------------------------------------------------------

@router.get("/{provider_id}", response_model=ProviderRead)
async def get_provider(
    provider_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProviderRead:
    """Fetch a single provider by ID (tenant-scoped; 404 if not found or cross-tenant)."""
    return await provider_service.get_provider(db, user, provider_id)


@router.patch("/{provider_id}", response_model=ProviderRead)
async def update_provider(
    provider_id: uuid.UUID,
    payload: ProviderUpdate,
    user: CurrentUser = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> ProviderRead:
    """Partially update a provider (requires provider:manage).

    Only supplied fields are changed; omitted fields remain unchanged.
    Returns 404 if the provider is not in the caller's tenant.
    """
    return await provider_service.update_provider(db, user, provider_id, payload)


# ---------------------------------------------------------------------------
# Contact log
# ---------------------------------------------------------------------------

@router.get("/{provider_id}/contacts", response_model=list[ProviderContactRead])
async def list_provider_contacts(
    provider_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProviderContactRead]:
    """Return all contact-log entries for a provider, newest first.

    Returns 404 if the provider is not in the caller's tenant.
    """
    return await provider_service.list_contacts(db, user, provider_id)


@router.post("/{provider_id}/contacts", response_model=ProviderContactRead, status_code=201)
async def create_provider_contact(
    provider_id: uuid.UUID,
    payload: ProviderContactCreate,
    user: CurrentUser = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> ProviderContactRead:
    """Log a provider interaction (call / email / meeting / note).

    Requires provider:manage. contacted_at defaults to UTC now when omitted.
    Returns 404 if the provider is not in the caller's tenant.
    """
    return await provider_service.create_contact(db, user, provider_id, payload)


# ---------------------------------------------------------------------------
# Delete a contact entry (separate prefix to avoid path collision)
# ---------------------------------------------------------------------------

_contact_router = APIRouter(prefix="/provider-contacts", tags=["providers"])


@_contact_router.delete("/{contact_id}", status_code=204)
async def delete_provider_contact(
    contact_id: uuid.UUID,
    user: CurrentUser = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a provider contact-log entry (requires provider:manage).

    Tenant-scoped; returns 404 if not found or cross-tenant.
    """
    await provider_service.delete_contact(db, user, contact_id)


# Expose the secondary router so the tech-lead can include it in router.py.
contact_router = _contact_router
