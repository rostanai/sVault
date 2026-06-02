"""Entitlements during trial — a trialing subscription must honor its linked plan.

Regression: an Enterprise trial previously fell back to generic Pro defaults
(sso=False), silently downgrading Enterprise-only features during the 14-day trial.
get_entitlements must return the linked plan's entitlements when one is attached, and
only fall back to the Pro trial defaults when the trial has no plan.
"""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

_TID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _scalar(val):
    r = MagicMock()
    r.scalar_one_or_none = MagicMock(return_value=val)
    return r


def _sub(status, *, plan_id=None, trial_ends_at=None):
    s = MagicMock()
    s.status = status
    s.plan_id = plan_id
    s.tenant_id = _TID
    s.trial_ends_at = trial_ends_at
    return s


@pytest.mark.asyncio
async def test_trialing_with_plan_honors_plan_entitlements():
    """Trialing sub attached to a plan → that plan's entitlements (e.g. SSO)."""
    from app.services.entitlements import get_entitlements

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    plan_id = uuid.UUID("00000000-0000-0000-0000-000000000010")

    ent = {
        "features": {"sso": True, "rag": True, "api": True, "mfa": True},
        "limits": {"policies": -1, "users": -1},
    }
    sub = _sub("trialing", plan_id=plan_id,
               trial_ends_at=datetime.now(UTC) + timedelta(days=7))
    sub.tenant_id = tenant_id
    plan = MagicMock()
    plan.id = plan_id
    plan.entitlements = ent

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_scalar(sub), _scalar(plan)])

    result = await get_entitlements(db, tenant_id)
    assert result is ent
    assert result["features"]["sso"] is True


@pytest.mark.asyncio
async def test_trialing_without_plan_falls_back_to_pro():
    """Trialing sub with no plan_id → generic Pro trial defaults."""
    from app.services.entitlements import _PRO_ENTITLEMENTS, get_entitlements

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    sub = _sub("trialing", trial_ends_at=datetime.now(UTC) + timedelta(days=7))

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_scalar(sub)])

    result = await get_entitlements(db, tenant_id)
    assert result is _PRO_ENTITLEMENTS


@pytest.mark.asyncio
async def test_active_trial_not_locked():
    """Trial whose trial_ends_at is in the future → full access, not locked."""
    from app.services.entitlements import _PRO_ENTITLEMENTS, resolve_entitlements

    sub = _sub("trialing", trial_ends_at=datetime.now(UTC) + timedelta(days=5))
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_scalar(sub)])

    ents, locked, status = await resolve_entitlements(db, _TID)
    assert ents is _PRO_ENTITLEMENTS
    assert locked is False
    assert status == "trialing"


@pytest.mark.asyncio
async def test_expired_trial_is_locked():
    """Trial past trial_ends_at (DB row still 'trialing') → locked, all features off."""
    from app.services.entitlements import _LOCKED_ENTITLEMENTS, resolve_entitlements

    sub = _sub("trialing", trial_ends_at=datetime.now(UTC) - timedelta(seconds=1))
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_scalar(sub)])

    ents, locked, status = await resolve_entitlements(db, _TID)
    assert ents is _LOCKED_ENTITLEMENTS
    assert locked is True
    assert status == "expired"
    assert ents["features"]["rag"] is False
    assert ents["features"]["email_alerts"] is False
    assert ents["limits"]["policies"] == 0


@pytest.mark.asyncio
async def test_expired_status_sub_is_locked():
    """Sub with status='expired' (set by the daily cron) → locked."""
    from app.services.entitlements import _LOCKED_ENTITLEMENTS, resolve_entitlements

    sub = _sub("expired")
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_scalar(sub)])

    ents, locked, status = await resolve_entitlements(db, _TID)
    assert ents is _LOCKED_ENTITLEMENTS
    assert locked is True
    assert status == "expired"


@pytest.mark.asyncio
async def test_cancelled_sub_falls_back_to_free():
    """Cancelled subscription → free tier (keeps basic email-alert access), not locked."""
    from app.services.entitlements import _FREE_ENTITLEMENTS, resolve_entitlements

    sub = _sub("cancelled")
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_scalar(sub)])

    ents, locked, status = await resolve_entitlements(db, _TID)
    assert ents is _FREE_ENTITLEMENTS
    assert locked is False
    assert status == "cancelled"


@pytest.mark.asyncio
async def test_active_paid_plan_not_locked():
    """Active sub with a populated plan → that plan's entitlements, not locked."""
    from app.services.entitlements import resolve_entitlements

    ent = {"features": {"rag": True}, "limits": {"policies": -1}}
    plan = MagicMock()
    plan.id = uuid.UUID("00000000-0000-0000-0000-000000000010")
    plan.entitlements = ent
    sub = _sub("active", plan_id=plan.id)
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_scalar(sub), _scalar(plan)])

    ents, locked, status = await resolve_entitlements(db, _TID)
    assert ents is ent
    assert locked is False
    assert status == "active"
