"""Tests for policy premium instalment endpoints and service layer.

Coverage
--------
1. Endpoint auth guards — every instalment route returns 401 without a token.
2. Service-layer unit tests (no live DB — AsyncMock throughout):
   a. create() — happy path: inserts instalment with status=pending.
   b. list_for_policy() — returns the instalment after create().
   c. mark_paid() — sets status=paid and paid_at (non-None datetime).
   d. cross-tenant mark_paid() — raises 404 (not 403).
   e. delete() — calls db.delete + commit.
3. Permission-matrix checks for policy:read / policy:update.

All service tests mock the DB session and policy_service.get_policy; no network call needed.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI

from app.api.v1.installments import router as installments_router
from app.core.errors import AppError, register_error_handlers
from app.core.security import CurrentUser
from app.schemas.installment import InstallmentCreate
from app.services import installment_service

# ---------------------------------------------------------------------------
# Isolated test app — carries the installments router without requiring the
# full production router.py wiring (tech-lead wires that separately).
# ---------------------------------------------------------------------------
_test_app = FastAPI()
register_error_handlers(_test_app)
_test_app.include_router(installments_router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ORG_A    = "cccccccc-cccc-cccc-cccc-cccccccccccc"
NULL_UUID = "00000000-0000-0000-0000-000000000000"


def _user(
    role: str = "admin",
    tenant_id: str = TENANT_A,
    org_id: str = ORG_A,
    is_super_admin: bool = False,
) -> CurrentUser:
    return CurrentUser(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        org_id=org_id,
        role=role,
        is_super_admin=is_super_admin,
    )


def _policy_orm(tenant_id: str = TENANT_A, policy_id: uuid.UUID | None = None) -> MagicMock:
    obj = MagicMock()
    obj.id = policy_id or uuid.uuid4()
    obj.tenant_id = uuid.UUID(tenant_id)
    obj.org_id = uuid.UUID(ORG_A)
    return obj


def _installment_orm(
    installment_id: uuid.UUID | None = None,
    tenant_id: str = TENANT_A,
    policy_id: uuid.UUID | None = None,
    status: str = "pending",
) -> MagicMock:
    obj = MagicMock()
    obj.id = installment_id or uuid.uuid4()
    obj.tenant_id = uuid.UUID(tenant_id)
    obj.policy_id = policy_id or uuid.uuid4()
    obj.amount_inr = Decimal("10000.00")
    obj.due_date = date(2026, 6, 30)
    obj.status = status
    obj.paid_at = None
    obj.note = None
    obj.created_at = datetime.now(UTC)
    return obj


# ---------------------------------------------------------------------------
# 1. Endpoint auth guards — 401 without bearer token
# ---------------------------------------------------------------------------

POLICY_UUID = str(uuid.uuid4())
INST_UUID = str(uuid.uuid4())


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", [
    ("get",    f"/api/v1/policies/{POLICY_UUID}/installments", None),
    ("post",   f"/api/v1/policies/{POLICY_UUID}/installments",
     {"amount_inr": "1000.00", "due_date": "2026-06-30"}),
    ("post",   f"/api/v1/installments/{INST_UUID}/pay", None),
    ("delete", f"/api/v1/installments/{INST_UUID}", None),
])
async def test_installment_endpoints_require_auth(method: str, path: str, body):
    """Every instalment endpoint must return 401 without a bearer token."""
    transport = httpx.ASGITransport(app=_test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        kwargs = {"json": body} if body is not None else {}
        resp = await getattr(ac, method)(path, **kwargs)

    assert resp.status_code == 401, (
        f"{method.upper()} {path} returned {resp.status_code}, expected 401"
    )
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 2a. create() — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_installment_happy_path():
    """create() should add an Installment with status=pending, inherit tenant from policy."""
    user = _user(role="admin")
    policy = _policy_orm(tenant_id=TENANT_A)
    payload = InstallmentCreate(amount_inr=Decimal("5000.00"), due_date=date(2026, 7, 15))

    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    captured: list = []

    async def fake_refresh(obj):
        captured.append(obj)

    db.refresh = fake_refresh

    _mock_get = AsyncMock(return_value=policy)
    with patch.object(installment_service.policy_service, "get_policy", _mock_get):
        await installment_service.create(db, user, policy.id, payload)

    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    assert len(captured) == 1

    added = db.add.call_args[0][0]
    assert added.status == "pending"
    assert added.tenant_id == uuid.UUID(TENANT_A)
    assert added.policy_id == policy.id
    assert added.amount_inr == Decimal("5000.00")
    assert added.due_date == date(2026, 7, 15)
    assert added.paid_at is None


# ---------------------------------------------------------------------------
# 2b. list_for_policy() — returns the created installment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_for_policy_returns_installments():
    """list_for_policy() should execute a query and return results after policy scope check."""
    user = _user(role="admin")
    policy = _policy_orm(tenant_id=TENANT_A)
    inst = _installment_orm(tenant_id=TENANT_A, policy_id=policy.id)

    # Fake scalars().all() result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [inst]

    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    _mock_get = AsyncMock(return_value=policy)
    with patch.object(installment_service.policy_service, "get_policy", _mock_get):
        results = await installment_service.list_for_policy(db, user, policy.id)

    assert len(results) == 1
    assert results[0].id == inst.id
    db.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# 2c. mark_paid() — sets status=paid + paid_at
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_paid_sets_status_and_paid_at():
    """mark_paid() must set status='paid' and a non-None paid_at timestamp."""
    user = _user(role="manager", tenant_id=TENANT_A)
    inst = _installment_orm(tenant_id=TENANT_A, status="pending")

    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch.object(
        installment_service, "_load_installment", AsyncMock(return_value=inst)
    ):
        await installment_service.mark_paid(db, user, inst.id)

    assert inst.status == "paid"
    assert inst.paid_at is not None
    assert isinstance(inst.paid_at, datetime)
    db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 2d. cross-tenant mark_paid() → 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_paid_cross_tenant_raises_404():
    """Trying to pay an instalment from a different tenant must raise not_found (404)."""
    # User is from TENANT_A; instalment_id is valid UUID but _load_installment returns None
    # because the tenant filter excludes it.
    user = _user(role="admin", tenant_id=TENANT_A)
    foreign_id = uuid.uuid4()

    # Simulate _load_installment finding nothing (cross-tenant → scalar_one_or_none → None)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(AppError) as exc_info:
        await installment_service.mark_paid(db, user, foreign_id)

    assert exc_info.value.code.value == "not_found"


# ---------------------------------------------------------------------------
# 2e. delete() — calls db.delete + commit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_installment_calls_delete_and_commit():
    """delete() should call db.delete on the loaded instalment and commit."""
    user = _user(role="admin", tenant_id=TENANT_A)
    inst = _installment_orm(tenant_id=TENANT_A)

    db = AsyncMock()
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    with patch.object(
        installment_service, "_load_installment", AsyncMock(return_value=inst)
    ):
        await installment_service.delete(db, user, inst.id)

    db.delete.assert_awaited_once_with(inst)
    db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 3. Permission-matrix checks
# ---------------------------------------------------------------------------

from app.core.authz import has_permission  # noqa: E402


@pytest.mark.parametrize("role,perm,expected", [
    # policy:read — all tenant roles
    ("admin",   "policy:read",   True),
    ("manager", "policy:read",   True),
    ("owner",   "policy:read",   True),
    ("viewer",  "policy:read",   True),
    # policy:update — admin / manager / owner (not viewer)
    ("admin",   "policy:update", True),
    ("manager", "policy:update", True),
    ("owner",   "policy:update", True),
    ("viewer",  "policy:update", False),
])
def test_installment_permission_matrix(role: str, perm: str, expected: bool):
    """Verify the authz matrix used by installment endpoints matches PERMISSIONS.md."""
    assert has_permission(_user(role=role), perm) is expected
