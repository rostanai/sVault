"""M6 approval-workflow tests.

Coverage
--------
1. Endpoint auth guards — every approval route returns 401 without a token.
2. Service-layer unit tests (no DB):
   a. submit() — creates an Approval with correct defaults.
   b. decide() — self-approval blocked if caller lacks `approve:self`.
   c. decide() — already-decided approval raises 409.
   d. decide() — approve path sets status=approved, is_self_approval=False when
      requester != approver.
   e. decide() — self-approval succeeds when caller HAS `approve:self`.
3. Permission-matrix checks for approval:submit, approval:approve, approve:self.

All service tests use AsyncMock / MagicMock and do NOT require a live DB.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.errors import AppError
from app.core.security import CurrentUser
from app.main import app
from app.schemas.approval import ApprovalCreate
from app.services import approval_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(
    role: str = "admin",
    user_id: str | None = None,
    tenant_id: str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    org_id: str = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    is_super_admin: bool = False,
) -> CurrentUser:
    return CurrentUser(
        user_id=user_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        org_id=org_id,
        role=role,
        is_super_admin=is_super_admin,
    )


def _approval_orm(
    approval_id: uuid.UUID | None = None,
    requested_by: uuid.UUID | None = None,
    status: str = "pending",
) -> MagicMock:
    """Minimal Approval ORM stub."""
    obj = MagicMock()
    obj.id = approval_id or uuid.uuid4()
    obj.tenant_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    obj.org_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    obj.action_type = "renewal"
    obj.entity_type = "policy"
    obj.entity_id = uuid.uuid4()
    obj.amount_inr = None
    obj.status = status
    obj.requested_by = requested_by
    obj.approver_id = None
    obj.is_self_approval = False
    obj.reason = None
    obj.decided_at = None
    obj.created_at = datetime.now(UTC)
    return obj


# ---------------------------------------------------------------------------
# 1. Endpoint auth guards — 401 without bearer token
# ---------------------------------------------------------------------------

NULL_UUID = "00000000-0000-0000-0000-000000000000"


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/v1/approvals",
     {"action_type": "other", "entity_type": "policy", "entity_id": NULL_UUID}),
    ("get", "/api/v1/approvals", None),
    ("post", f"/api/v1/approvals/{NULL_UUID}/approve", {}),
    ("post", f"/api/v1/approvals/{NULL_UUID}/reject", {}),
])
async def test_approval_endpoints_require_auth(method: str, path: str, body: dict | None):
    """Every approval endpoint must reject requests without a bearer token with 401."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        kwargs = {"json": body} if body is not None else {}
        resp = await getattr(ac, method)(path, **kwargs)

    assert resp.status_code == 401, f"{method.upper()} {path} should be 401 without auth"
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 2a. submit() — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_creates_pending_approval():
    """submit() should persist a Approval with status=pending and correct tenant/org/user."""
    user = _user(role="owner")
    payload = ApprovalCreate(
        action_type="new_policy",
        entity_type="policy",
        entity_id=uuid.uuid4(),
        amount_inr=None,
    )

    # Fake async DB session
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    # db.refresh sets properties on the passed object so we capture it.
    captured: list = []

    async def fake_refresh(obj):
        captured.append(obj)

    db.refresh = fake_refresh

    await approval_service.submit(db, user, payload)

    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    assert len(captured) == 1

    added: MagicMock = db.add.call_args[0][0]
    assert added.status == "pending"
    assert str(added.tenant_id) == user.tenant_id
    assert str(added.requested_by) == user.user_id
    assert added.action_type == "new_policy"
    assert added.entity_type == "policy"
    assert added.is_self_approval is False


# ---------------------------------------------------------------------------
# 2b. decide() — self-approval blocked without approve:self
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decide_self_approval_blocked_without_permission():
    """An Owner trying to approve their own request must be rejected with 403."""
    owner_id = uuid.uuid4()
    user = _user(role="owner", user_id=str(owner_id))
    approval = _approval_orm(requested_by=owner_id, status="pending")

    db = AsyncMock()

    # _load_approval will be patched so we bypass DB queries.
    with patch.object(approval_service, "_load_approval", AsyncMock(return_value=approval)):
        with pytest.raises(AppError) as exc_info:
            await approval_service.decide(
                db, user, approval.id, approve=True, reason=None
            )

    assert exc_info.value.code.value == "forbidden"
    assert "self-approval" in exc_info.value.message.lower()


# ---------------------------------------------------------------------------
# 2c. decide() — already-decided raises 409
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decide_already_decided_raises_conflict():
    """Calling decide() on an already-approved approval must raise 409."""
    user = _user(role="admin")
    approval = _approval_orm(status="approved")

    db = AsyncMock()

    with patch.object(approval_service, "_load_approval", AsyncMock(return_value=approval)):
        with pytest.raises(AppError) as exc_info:
            await approval_service.decide(
                db, user, approval.id, approve=True, reason=None
            )

    assert exc_info.value.code.value == "conflict"


@pytest.mark.asyncio
async def test_decide_already_rejected_raises_conflict():
    """Calling decide() on an already-rejected approval must also raise 409."""
    user = _user(role="manager")
    approval = _approval_orm(status="rejected")

    db = AsyncMock()

    with patch.object(approval_service, "_load_approval", AsyncMock(return_value=approval)):
        with pytest.raises(AppError) as exc_info:
            await approval_service.decide(
                db, user, approval.id, approve=False, reason="final"
            )

    assert exc_info.value.code.value == "conflict"


# ---------------------------------------------------------------------------
# 2d. decide() — approve by a different user (not self-approval)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decide_approve_by_different_user():
    """Admin approving someone else's request should succeed with is_self_approval=False."""
    requester_id = uuid.uuid4()
    approver = _user(role="admin")  # different user_id
    approval = _approval_orm(requested_by=requester_id, status="pending")

    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch.object(approval_service, "_load_approval", AsyncMock(return_value=approval)):
        await approval_service.decide(
            db, approver, approval.id, approve=True, reason="looks good"
        )

    assert approval.status == "approved"
    assert approval.is_self_approval is False
    assert approval.reason == "looks good"
    assert approval.decided_at is not None
    db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 2e. decide() — self-approval succeeds with approve:self
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decide_self_approval_allowed_for_admin():
    """Admin (who has approve:self) approving their own request should succeed."""
    admin_id = uuid.uuid4()
    user = _user(role="admin", user_id=str(admin_id))
    approval = _approval_orm(requested_by=admin_id, status="pending")

    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch.object(approval_service, "_load_approval", AsyncMock(return_value=approval)):
        await approval_service.decide(
            db, user, approval.id, approve=True, reason="self-approved"
        )

    assert approval.status == "approved"
    assert approval.is_self_approval is True
    assert str(approval.approver_id) == str(admin_id)


# ---------------------------------------------------------------------------
# 3. Permission-matrix checks (no DB)
# ---------------------------------------------------------------------------

from app.core.authz import has_permission  # noqa: E402 — after service imports


@pytest.mark.parametrize("role,perm,expected", [
    # approval:submit — admin/manager/owner can submit, viewer cannot
    ("admin",   "approval:submit",  True),
    ("manager", "approval:submit",  True),
    ("owner",   "approval:submit",  True),
    ("viewer",  "approval:submit",  False),
    # approval:approve — only admin/manager
    ("admin",   "approval:approve", True),
    ("manager", "approval:approve", True),
    ("owner",   "approval:approve", False),
    ("viewer",  "approval:approve", False),
    # approve:self — admin/manager only
    ("admin",   "approve:self",     True),
    ("manager", "approve:self",     True),
    ("owner",   "approve:self",     False),
    ("viewer",  "approve:self",     False),
])
def test_approval_permission_matrix(role: str, perm: str, expected: bool):
    """Verify the authz matrix matches docs/PERMISSIONS.md for approval actions."""
    assert has_permission(_user(role=role), perm) is expected


# ---------------------------------------------------------------------------
# 4. list_approvals — no tenant returns empty list (no DB needed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_approvals_no_tenant_returns_empty():
    """A user with no tenant_id should get an empty list, not an error."""
    user = CurrentUser(user_id="x", tenant_id=None, org_id=None, role="admin")
    db = AsyncMock()
    result = await approval_service.list_approvals(db, user)
    assert result == []
    db.execute.assert_not_awaited()
