"""Tests for provider detail + contact-log endpoints and service.

Coverage
--------
1. Auth guards — every new route returns 401 without a token.
2. Service — add a contact and list returns it (mocked DB).
3. Service — cross-tenant get_provider raises 404 (mocked DB).
4. Service — invalid kind rejected by Pydantic at schema level.
5. Service — delete_contact raises 404 when contact not in tenant (mocked DB).
6. Endpoint — PATCH /providers/{id} requires provider:manage (403 for viewer).

All service tests use AsyncMock / MagicMock — no live DB required.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.api.v1 import providers as providers_module
from app.core.errors import AppError, ErrorCode, register_error_handlers
from app.core.middleware import RequestIDMiddleware
from app.core.security import CurrentUser
from app.schemas.provider_contact import ProviderContactCreate, ProviderUpdate
from app.services import provider_service

# ---------------------------------------------------------------------------
# Minimal test app — only the providers routers (no live DB / router.py change).
# ---------------------------------------------------------------------------


def _make_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RequestIDMiddleware)
    register_error_handlers(test_app)
    test_app.include_router(providers_module.router, prefix="/api/v1")
    test_app.include_router(providers_module.contact_router, prefix="/api/v1")
    return test_app


_test_app = _make_test_app()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NULL_UUID = "00000000-0000-0000-0000-000000000000"

TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _user(
    role: str = "admin",
    tenant_id: str = TENANT_A,
    user_id: str | None = None,
) -> CurrentUser:
    return CurrentUser(
        user_id=user_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        org_id=str(uuid.uuid4()),
        role=role,
    )


def _provider_orm(tenant_id: str = TENANT_A) -> MagicMock:
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.tenant_id = uuid.UUID(tenant_id)
    obj.name = "National Insurance"
    obj.contact_name = "Ravi Kumar"
    obj.contact_email = "ravi@nationalins.com"
    obj.contact_phone = "+919876543210"
    obj.notes = None
    obj.created_at = datetime.now(UTC)
    obj.updated_at = datetime.now(UTC)
    return obj


def _contact_orm(
    provider_id: uuid.UUID | None = None,
    tenant_id: str = TENANT_A,
) -> MagicMock:
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.tenant_id = uuid.UUID(tenant_id)
    obj.provider_id = provider_id or uuid.uuid4()
    obj.kind = "call"
    obj.subject = "Renewal discussion"
    obj.note = "Agreed on 10% discount"
    obj.contacted_at = datetime.now(UTC)
    obj.created_by = uuid.uuid4()
    obj.created_at = datetime.now(UTC)
    return obj


# ---------------------------------------------------------------------------
# 1. Auth guards — 401 without bearer token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", [
    ("get",    f"/api/v1/providers/{NULL_UUID}",                    None),
    ("patch",  f"/api/v1/providers/{NULL_UUID}",                    {"name": "X"}),
    ("get",    f"/api/v1/providers/{NULL_UUID}/contacts",           None),
    ("post",   f"/api/v1/providers/{NULL_UUID}/contacts",           {"kind": "call"}),
    ("delete", f"/api/v1/provider-contacts/{NULL_UUID}",            None),
])
async def test_new_provider_routes_require_auth(method: str, path: str, body: dict | None):
    """Every new provider/contact route must return 401 without a Bearer token."""
    transport = httpx.ASGITransport(app=_test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        kwargs = {"json": body} if body is not None else {}
        resp = await getattr(ac, method)(path, **kwargs)

    assert resp.status_code == 401, f"{method.upper()} {path} should be 401 without auth"
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 2. Service — add a contact then list returns it
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_contact_then_list_returns_it():
    """create_contact() persists a ProviderContact; list_contacts() returns it."""
    user = _user()
    provider = _provider_orm()
    provider_id = provider.id
    contact = _contact_orm(provider_id=provider_id)

    db = AsyncMock()

    # Scalar result for get_provider (called inside create_contact)
    scalar_provider = MagicMock()
    scalar_provider.scalar_one_or_none = MagicMock(return_value=provider)

    # Scalar result for listing contacts
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=[contact])
    scalar_contacts = MagicMock()
    scalar_contacts.scalars = MagicMock(return_value=scalars_mock)

    # db.execute returns provider lookup first, then contacts listing
    db.execute = AsyncMock(side_effect=[scalar_provider, scalar_provider, scalar_contacts])
    db.add = MagicMock()
    db.commit = AsyncMock()

    async def fake_refresh(obj):
        pass

    db.refresh = fake_refresh

    payload = ProviderContactCreate(kind="call", subject="Renewal discussion")
    await provider_service.create_contact(db, user, provider_id, payload)

    db.add.assert_called_once()
    db.commit.assert_awaited()

    # list_contacts
    contacts = await provider_service.list_contacts(db, user, provider_id)
    assert len(contacts) == 1
    assert contacts[0].kind == "call"


# ---------------------------------------------------------------------------
# 3. Service — cross-tenant get_provider raises 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_provider_cross_tenant_raises_404():
    """get_provider() must raise not_found when the provider belongs to another tenant."""
    user = _user(tenant_id=TENANT_A)

    db = AsyncMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=None)  # not found
    db.execute = AsyncMock(return_value=scalar_result)

    with pytest.raises(AppError) as exc_info:
        await provider_service.get_provider(db, user, uuid.uuid4())

    assert exc_info.value.code == ErrorCode.not_found


# ---------------------------------------------------------------------------
# 4. Schema — invalid kind rejected by Pydantic
# ---------------------------------------------------------------------------

def test_invalid_contact_kind_rejected():
    """ProviderContactCreate with kind not in {call,email,meeting,note} must fail validation."""
    with pytest.raises(ValidationError):
        ProviderContactCreate(kind="fax")  # type: ignore[arg-type]


def test_valid_contact_kinds_accepted():
    """All four valid kinds must pass Pydantic validation."""
    for kind in ("call", "email", "meeting", "note"):
        pc = ProviderContactCreate(kind=kind)  # type: ignore[arg-type]
        assert pc.kind == kind


# ---------------------------------------------------------------------------
# 5. Service — delete_contact raises 404 when not in tenant
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_contact_cross_tenant_raises_404():
    """delete_contact() must raise not_found when the contact is not in the user's tenant."""
    user = _user(tenant_id=TENANT_A)

    db = AsyncMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=scalar_result)

    with pytest.raises(AppError) as exc_info:
        await provider_service.delete_contact(db, user, uuid.uuid4())

    assert exc_info.value.code == ErrorCode.not_found


# ---------------------------------------------------------------------------
# 6. Endpoint — PATCH requires provider:manage (viewer gets 403)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_provider_requires_manage_permission():
    """A viewer-role user must receive 403 when trying to PATCH a provider."""
    viewer = _user(role="viewer")

    def _fake_decode(token: str) -> CurrentUser:
        return viewer

    # Patch decode_token where authz.py resolves it (its own namespace).
    with patch("app.core.authz.decode_token", side_effect=_fake_decode):
        transport = httpx.ASGITransport(app=_test_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.patch(
                f"/api/v1/providers/{NULL_UUID}",
                json={"name": "Updated Name"},
                headers={"Authorization": "Bearer fake-token"},
            )

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


# ---------------------------------------------------------------------------
# 7. Service — update_provider applies only supplied fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_provider_applies_partial_fields():
    """update_provider() must set only the fields present in the payload."""
    user = _user()
    provider = _provider_orm()
    provider.name = "Old Name"

    db = AsyncMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=provider)
    db.execute = AsyncMock(return_value=scalar_result)
    db.commit = AsyncMock()

    async def fake_refresh(obj):
        pass

    db.refresh = fake_refresh

    payload = ProviderUpdate(name="New Name")
    updated = await provider_service.update_provider(db, user, provider.id, payload)

    assert updated.name == "New Name"
    db.commit.assert_awaited_once()
