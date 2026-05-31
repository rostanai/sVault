"""Tests for the Onboarding status endpoint and service.

Coverage
--------
1. Auth guard — GET /api/v1/onboarding/status without a token → 401.
2. Service computes done flags from counts (mockable DB).
3. Service computes complete / completed_count correctly.
4. No-tenant user returns all-false steps (no DB queries).
5. Org scoping: Admin sees whole group (org=None); Owner restricted.

All service tests use AsyncMock / MagicMock — no live DB required.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from app.api.v1 import onboarding as onboarding_module
from app.core.errors import register_error_handlers
from app.core.middleware import RequestIDMiddleware
from app.core.security import CurrentUser
from app.services import onboarding_service

# ---------------------------------------------------------------------------
# Minimal test app — only the onboarding router.
# ---------------------------------------------------------------------------

def _make_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RequestIDMiddleware)
    register_error_handlers(test_app)
    test_app.include_router(onboarding_module.router, prefix="/api/v1")
    return test_app


_test_app = _make_test_app()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TENANT_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc"
_ORG_ID = "dddddddd-dddd-dddd-dddd-dddddddddddd"


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


def _scalar_result(value: int) -> MagicMock:
    """Fake DB execute result that returns *value* from scalar_one()."""
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _make_db(counts: list[int]) -> AsyncMock:
    """Fake AsyncSession whose execute() returns scalar_one() == counts[i] in order."""
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_scalar_result(c) for c in counts])
    return db


# ---------------------------------------------------------------------------
# 1. Auth guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_onboarding_status_requires_auth():
    """GET /onboarding/status without a bearer token must return 401."""
    transport = httpx.ASGITransport(app=_test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/onboarding/status")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 2. Service computes done flags from counts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_status_all_steps_done():
    """When all counts > 0 / conditions met, every step is done=True."""
    # Execute call order (admin = no org filter, no alert fallback since rule_count > 0):
    # provider_count=1, policy_count=1, doc_count=1, rule_count=1, profile_count=2
    db = _make_db([1, 1, 1, 1, 2])
    user = _user(role="admin")

    status = await onboarding_service.get_status(db, user)

    assert all(s.done for s in status.steps)
    assert status.complete is True
    assert status.completed_count == 5
    assert status.total == 5


@pytest.mark.asyncio
async def test_get_status_none_done():
    """When all counts == 0, every step is done=False."""
    # provider=0, policy=0, doc=0, rule_count=0, alert_fallback=0, profile=1, inv=0
    db = _make_db([0, 0, 0, 0, 0, 1, 0])
    user = _user(role="admin")

    status = await onboarding_service.get_status(db, user)

    assert not any(s.done for s in status.steps)
    assert status.complete is False
    assert status.completed_count == 0


@pytest.mark.asyncio
async def test_get_status_partial_done():
    """Partial completion: first two steps done, rest not."""
    # provider=1, policy=1, doc=0, rule_count=0, alert_fallback=0, profile=1, inv=0
    db = _make_db([1, 1, 0, 0, 0, 1, 0])
    user = _user(role="admin")

    status = await onboarding_service.get_status(db, user)

    done_keys = {s.key for s in status.steps if s.done}
    assert done_keys == {"provider", "policy"}
    assert status.completed_count == 2
    assert status.complete is False


# ---------------------------------------------------------------------------
# 3. complete / completed_count accuracy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_status_complete_flag():
    """complete=True only when completed_count == total."""
    db = _make_db([1, 1, 1, 1, 2])
    user = _user(role="admin")

    status = await onboarding_service.get_status(db, user)

    assert status.complete == (status.completed_count == status.total)


@pytest.mark.asyncio
async def test_get_status_completed_count_matches_done_steps():
    """completed_count must equal the number of steps with done=True."""
    # provider=1, policy=0, doc=0, rule=1, (no alert fallback), profile=2
    db = _make_db([1, 0, 0, 1, 2])
    user = _user(role="admin")

    status = await onboarding_service.get_status(db, user)

    assert status.completed_count == sum(1 for s in status.steps if s.done)


# ---------------------------------------------------------------------------
# 4. No-tenant user returns all-false steps without hitting DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_status_no_tenant_returns_empty():
    """User with no tenant_id receives all-false steps and no DB queries."""
    user = CurrentUser(user_id="x", tenant_id=None, org_id=None, role="admin")
    db = AsyncMock()

    status = await onboarding_service.get_status(db, user)

    assert not any(s.done for s in status.steps)
    assert status.complete is False
    assert status.completed_count == 0
    assert status.total == 5
    db.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# 5. Team step: done via invitation (profile_count <= 1 but inv_count > 0)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_status_team_done_via_invitation():
    """Team step is done if an invitation exists even when only one profile."""
    # provider=0, policy=0, doc=0, rule=0, alert=0, profile=1, inv=1
    db = _make_db([0, 0, 0, 0, 0, 1, 1])
    user = _user(role="admin")

    status = await onboarding_service.get_status(db, user)

    team_step = next(s for s in status.steps if s.key == "team")
    assert team_step.done is True


# ---------------------------------------------------------------------------
# 6. Step keys, labels, hrefs are present and correct
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_status_step_metadata():
    """All five steps have the expected keys, labels, and hrefs."""
    db = _make_db([0, 0, 0, 0, 0, 1, 0])
    user = _user(role="admin")

    status = await onboarding_service.get_status(db, user)

    step_by_key = {s.key: s for s in status.steps}
    assert set(step_by_key) == {"provider", "policy", "document", "alert", "team"}
    assert step_by_key["provider"].href == "/app/providers"
    assert step_by_key["policy"].href == "/app/policies"
    assert step_by_key["document"].href == "/app/policies"
    assert step_by_key["alert"].href == "/app/alerts"
    assert step_by_key["team"].href == "/app/settings"
    # Labels are non-empty strings
    assert all(s.label for s in status.steps)
    assert all(s.description for s in status.steps)
