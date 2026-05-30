"""M4 alert-engine tests — due-day logic (timezone), rule resolution, guards."""
from datetime import date, timedelta

import httpx
import pytest

from app.main import app
from app.services import notifier
from app.services.alert_engine import (
    DEFAULT_CHANNELS,
    DEFAULT_LEAD_DAYS,
    build_message,
    due_lead_days,
    resolve_rule,
)


def test_due_lead_days_matches_exact_offsets():
    today = date(2026, 6, 1)
    # expiry 30 days out -> only the 30-day reminder is due today
    assert due_lead_days(today + timedelta(days=30), today, DEFAULT_LEAD_DAYS) == [30]
    # expiry 1 day out -> the 1-day reminder
    assert due_lead_days(today + timedelta(days=1), today, DEFAULT_LEAD_DAYS) == [1]
    # expiry 45 days out -> nothing due today
    assert due_lead_days(today + timedelta(days=45), today, DEFAULT_LEAD_DAYS) == []
    # already expired -> nothing
    assert due_lead_days(today - timedelta(days=2), today, DEFAULT_LEAD_DAYS) == []


def test_resolve_rule_defaults_and_override():
    assert resolve_rule(None, None) == (DEFAULT_LEAD_DAYS, DEFAULT_CHANNELS)

    class R:
        lead_days = [90, 30]
        channels = ["email"]

    # per-policy wins over tenant default
    assert resolve_rule(R(), None) == ([90, 30], ["email"])


def test_build_message_mentions_policy_and_days():
    class P:
        title = "Factory Fire Cover"
        category = "factory_property"
        expiry_date = date(2026, 7, 1)

    msg = build_message(P(), 30)
    assert "Factory Fire Cover" in msg and "30 day" in msg


@pytest.mark.asyncio
async def test_channels_simulated_when_unconfigured():
    # No creds in test env -> simulated, never silently "sent"
    assert notifier.channel_configured("whatsapp") is False
    res = await notifier.send("email", "owner@example.com", "hi")
    assert res.status == "simulated"
    res2 = await notifier.send("email", None, "hi")
    assert res2.status == "failed"  # no recipient


@pytest.mark.asyncio
async def test_dispatch_requires_cron_secret():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/alerts/dispatch")
    # No X-Cron-Secret -> endpoint is hidden (404), before any DB access.
    assert resp.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/alerts"),
    ("put", "/api/v1/policies/00000000-0000-0000-0000-000000000000/alert-rule"),
])
async def test_alert_endpoints_require_auth(method, path):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        kwargs = {"json": {}} if method == "put" else {}
        resp = await getattr(ac, method)(path, **kwargs)
    assert resp.status_code == 401
