"""M1 service-logic unit tests (no DB) + endpoint auth-guard smoke tests."""
from datetime import UTC, datetime

import httpx
import pytest

from app.main import app
from app.services.onboarding import TRIAL_DAYS, trial_end
from app.services.org_service import is_group_wide


def test_trial_is_14_days():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    assert TRIAL_DAYS == 14
    assert (trial_end(start) - start).days == 14


def test_is_group_wide():
    assert is_group_wide("admin") and is_group_wide("manager")
    assert not is_group_wide("owner") and not is_group_wide("viewer")


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/auth/me"),
    ("get", "/api/v1/orgs"),
    ("post", "/api/v1/auth/onboard"),
    ("post", "/api/v1/invitations"),
])
async def test_protected_endpoints_require_auth(method, path):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        kwargs = {"json": {}} if method == "post" else {}
        resp = await getattr(ac, method)(path, **kwargs)
    # No bearer token -> 401 with the error envelope (before any DB access).
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"
