"""Entitlements during trial — a trialing subscription must honor its linked plan.

Regression: an Enterprise trial previously fell back to generic Pro defaults
(sso=False), silently downgrading Enterprise-only features during the 14-day trial.
get_entitlements must return the linked plan's entitlements when one is attached, and
only fall back to the Pro trial defaults when the trial has no plan.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


def _scalar(val):
    r = MagicMock()
    r.scalar_one_or_none = MagicMock(return_value=val)
    return r


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
    sub = MagicMock()
    sub.status = "trialing"
    sub.plan_id = plan_id
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
    sub = MagicMock()
    sub.status = "trialing"
    sub.plan_id = None
    sub.tenant_id = tenant_id

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_scalar(sub)])

    result = await get_entitlements(db, tenant_id)
    assert result is _PRO_ENTITLEMENTS
