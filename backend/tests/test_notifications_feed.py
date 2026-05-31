"""Tests for the Notifications feed endpoint and service.

Coverage
--------
1. Auth guard — GET /api/v1/notifications without a token → 401.
2. Service merges unacked alerts + pending approvals, newest first.
3. Service computes correct unread_count (total, not capped by display).
4. Service caps displayed items at 20.
5. unread_count is capped at 99 when total > 99.
6. No-tenant user returns empty feed without hitting DB.
7. Policy titles are resolved via a single batched lookup.

All service tests use AsyncMock / MagicMock — no live DB required.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from app.api.v1 import notifications as notif_module
from app.core.errors import register_error_handlers
from app.core.middleware import RequestIDMiddleware
from app.core.security import CurrentUser
from app.services import notification_feed_service

# ---------------------------------------------------------------------------
# Minimal test app — only the notifications router.
# ---------------------------------------------------------------------------

def _make_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RequestIDMiddleware)
    register_error_handlers(test_app)
    test_app.include_router(notif_module.router, prefix="/api/v1")
    return test_app


_test_app = _make_test_app()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_ORG_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
_NOW = datetime.now(UTC)


def _user(
    role: str = "admin",
    tenant_id: str = _TENANT_ID,
    org_id: str | None = _ORG_ID,
    is_super_admin: bool = False,
) -> CurrentUser:
    return CurrentUser(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        org_id=org_id,
        role=role,
        is_super_admin=is_super_admin,
    )


def _alert_orm(
    policy_id: uuid.UUID | None = None,
    lead_day: int = 30,
    channel: str = "email",
    created_at: datetime | None = None,
) -> MagicMock:
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.tenant_id = uuid.UUID(_TENANT_ID)
    obj.org_id = uuid.UUID(_ORG_ID)
    obj.policy_id = policy_id or uuid.uuid4()
    obj.lead_day = lead_day
    obj.channel = channel
    obj.status = "scheduled"
    obj.created_at = created_at or _NOW
    return obj


def _approval_orm(
    action_type: str = "renewal",
    entity_type: str = "policy",
    created_at: datetime | None = None,
) -> MagicMock:
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.tenant_id = uuid.UUID(_TENANT_ID)
    obj.org_id = uuid.UUID(_ORG_ID)
    obj.action_type = action_type
    obj.entity_type = entity_type
    obj.status = "pending"
    obj.created_at = created_at or _NOW
    return obj


def _policy_row(policy_id: uuid.UUID, title: str) -> MagicMock:
    row = MagicMock()
    row.id = policy_id
    row.title = title
    return row


def _make_db(alerts: list, approvals: list, policy_rows: list | None = None) -> AsyncMock:
    """Build a fake AsyncSession whose execute() returns results in sequence."""
    def _scalars(items):
        result = MagicMock()
        result.scalars.return_value.all.return_value = items
        return result

    def _rows(items):
        result = MagicMock()
        result.all.return_value = items
        return result

    db = AsyncMock()
    # Execution order: alerts → approvals → policy title lookup.
    db.execute = AsyncMock(side_effect=[
        _scalars(alerts),
        _scalars(approvals),
        _rows(policy_rows or []),
    ])
    return db


# ---------------------------------------------------------------------------
# 1. Auth guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notifications_requires_auth():
    """GET /notifications without a bearer token must return 401."""
    transport = httpx.ASGITransport(app=_test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/notifications")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 2. Service merges alerts + approvals, newest first
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_feed_merges_alerts_and_approvals_newest_first():
    """Feed items must interleave alerts and approvals sorted by created_at desc."""
    policy_id = uuid.uuid4()
    older = _NOW - timedelta(hours=2)
    newer = _NOW - timedelta(hours=1)

    alert = _alert_orm(policy_id=policy_id, lead_day=7, channel="whatsapp", created_at=older)
    approval = _approval_orm(action_type="new_policy", created_at=newer)
    policy_row = _policy_row(policy_id, "Fleet Insurance")

    db = _make_db([alert], [approval], [policy_row])
    user = _user()

    feed = await notification_feed_service.get_feed(db, user)

    assert feed.unread_count == 2
    assert len(feed.items) == 2
    # Newest first: approval (newer) then alert (older).
    assert feed.items[0].type == "approval"
    assert feed.items[1].type == "alert"

    # Check approval item content.
    appr_item = feed.items[0]
    assert "new policy" in appr_item.title.lower()
    assert appr_item.href == "/app/approvals"
    assert appr_item.subtitle == "policy"

    # Check alert item content.
    alert_item = feed.items[1]
    assert "Fleet Insurance" in alert_item.title
    assert "7d" in alert_item.subtitle
    assert "whatsapp" in alert_item.subtitle
    assert alert_item.href == "/app/alerts"


# ---------------------------------------------------------------------------
# 3. unread_count reflects the real total, not the display cap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unread_count_reflects_full_total():
    """unread_count == total alerts + approvals even when display is capped."""
    # 15 alerts + 10 approvals = 25 total, but only 20 displayed.
    alerts = [_alert_orm() for _ in range(15)]
    approvals = [_approval_orm() for _ in range(10)]
    policy_ids = {a.policy_id for a in alerts}
    policy_rows = [_policy_row(pid, f"Policy {i}") for i, pid in enumerate(policy_ids)]

    db = _make_db(alerts, approvals, policy_rows)
    user = _user()

    feed = await notification_feed_service.get_feed(db, user)

    assert feed.unread_count == 25
    assert len(feed.items) == 20  # capped


# ---------------------------------------------------------------------------
# 4. Display cap at 20
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_feed_caps_display_at_20():
    """Displayed items must never exceed 20 regardless of how many exist."""
    alerts = [
        _alert_orm(created_at=_NOW - timedelta(minutes=i))
        for i in range(25)
    ]
    policy_rows = [_policy_row(a.policy_id, f"Policy {i}") for i, a in enumerate(alerts)]

    db = _make_db(alerts, [], policy_rows)
    user = _user()

    feed = await notification_feed_service.get_feed(db, user)

    assert len(feed.items) <= 20


# ---------------------------------------------------------------------------
# 5. unread_count capped at 99
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unread_count_capped_at_99():
    """When total > 99, unread_count must be capped at 99."""
    alerts = [
        _alert_orm(created_at=_NOW - timedelta(seconds=i))
        for i in range(60)
    ]
    approvals = [
        _approval_orm(created_at=_NOW - timedelta(seconds=i))
        for i in range(60)
    ]
    policy_ids = {a.policy_id for a in alerts}
    policy_rows = [_policy_row(pid, f"Policy {i}") for i, pid in enumerate(policy_ids)]

    db = _make_db(alerts, approvals, policy_rows)
    user = _user()

    feed = await notification_feed_service.get_feed(db, user)

    assert feed.unread_count == 99  # capped
    assert len(feed.items) == 20    # display still capped at 20


# ---------------------------------------------------------------------------
# 6. No-tenant user returns empty feed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_feed_no_tenant_returns_empty():
    """A user with no tenant_id should receive an empty feed without any DB query."""
    user = CurrentUser(user_id="x", tenant_id=None, org_id=None, role="admin")
    db = AsyncMock()
    feed = await notification_feed_service.get_feed(db, user)
    assert feed.unread_count == 0
    assert feed.items == []
    db.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# 7. Policy titles resolved in ONE batched lookup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_policy_titles_batch_resolved():
    """Policy titles for all alert policy_ids are fetched in a single query."""
    pid1, pid2 = uuid.uuid4(), uuid.uuid4()
    alerts = [
        _alert_orm(policy_id=pid1),
        _alert_orm(policy_id=pid2),
    ]
    policy_rows = [
        _policy_row(pid1, "Machinery Insurance"),
        _policy_row(pid2, "Key Person Cover"),
    ]

    db = _make_db(alerts, [], policy_rows)
    user = _user()

    feed = await notification_feed_service.get_feed(db, user)

    titles = {item.title for item in feed.items}
    assert any("Machinery Insurance" in t for t in titles)
    assert any("Key Person Cover" in t for t in titles)

    # The DB should have been called exactly 3 times:
    # 1 → alerts, 2 → approvals, 3 → policy titles (single batch).
    assert db.execute.await_count == 3
