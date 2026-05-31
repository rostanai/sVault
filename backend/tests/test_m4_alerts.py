"""M4 alert-engine tests — due-day logic (timezone), rule resolution, guards,
snooze, mark-renewed, escalation."""
import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.security import CurrentUser
from app.main import app
from app.services import notifier
from app.services.alert_engine import (
    DEFAULT_CHANNELS,
    DEFAULT_LEAD_DAYS,
    build_message,
    due_lead_days,
    resolve_rule,
    snooze,
)

# ---------------------------------------------------------------------------
# helpers shared across new tests
# ---------------------------------------------------------------------------

def _make_user(
    tenant_id: str | None = None,
    org_id: str | None = None,
    role: str = "admin",
) -> CurrentUser:
    return CurrentUser(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id or str(uuid.uuid4()),
        org_id=org_id or str(uuid.uuid4()),
        role=role,
        is_super_admin=False,
    )


def _make_alert_obj(
    tenant_id: uuid.UUID | None = None,
    scheduled_for: date | None = None,
    status: str = "sent",
    acknowledged_by: uuid.UUID | None = None,
    acknowledged_at=None,
) -> MagicMock:
    alert = MagicMock()
    alert.id = uuid.uuid4()
    alert.tenant_id = tenant_id or uuid.uuid4()
    alert.scheduled_for = scheduled_for or date(2026, 8, 1)
    alert.status = status
    alert.acknowledged_by = acknowledged_by
    alert.acknowledged_at = acknowledged_at
    alert.policy_id = uuid.uuid4()
    alert.channel = "email"
    alert.lead_day = 7
    return alert


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


# ---------------------------------------------------------------------------
# Snooze — service-level unit tests (no real DB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_snooze_moves_scheduled_for_forward():
    """snooze() should push scheduled_for by N days and reset status to 'scheduled'."""
    tenant_id = uuid.uuid4()
    user = _make_user(tenant_id=str(tenant_id))
    original_date = date(2026, 8, 1)
    alert = _make_alert_obj(tenant_id=tenant_id, scheduled_for=original_date, status="sent")

    db = MagicMock()
    db.get = AsyncMock(return_value=alert)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    result = await snooze(db, user, alert.id, days=10)

    assert result is not None
    assert result.scheduled_for == original_date + timedelta(days=10)
    assert result.status == "scheduled"
    assert result.acknowledged_by is None
    assert result.acknowledged_at is None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_snooze_clears_acknowledgement():
    """snooze() should clear acknowledged_by/at fields."""
    tenant_id = uuid.uuid4()
    user = _make_user(tenant_id=str(tenant_id))
    alert = _make_alert_obj(
        tenant_id=tenant_id,
        status="acknowledged",
        acknowledged_by=uuid.uuid4(),
        acknowledged_at="2026-07-01T10:00:00+05:30",
    )

    db = MagicMock()
    db.get = AsyncMock(return_value=alert)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    result = await snooze(db, user, alert.id, days=5)

    assert result.status == "scheduled"
    assert result.acknowledged_by is None
    assert result.acknowledged_at is None


@pytest.mark.asyncio
async def test_snooze_returns_none_for_missing_alert():
    """snooze() returns None when the alert id doesn't exist."""
    user = _make_user()
    db = MagicMock()
    db.get = AsyncMock(return_value=None)

    result = await snooze(db, user, uuid.uuid4(), days=7)
    assert result is None


@pytest.mark.asyncio
async def test_snooze_returns_none_for_different_tenant():
    """snooze() returns None when alert belongs to a different tenant (never-reveal)."""
    user = _make_user(tenant_id=str(uuid.uuid4()))
    alert = _make_alert_obj(tenant_id=uuid.uuid4())  # different tenant

    db = MagicMock()
    db.get = AsyncMock(return_value=alert)

    result = await snooze(db, user, alert.id, days=5)
    assert result is None


# ---------------------------------------------------------------------------
# Snooze — endpoint auth guard (401)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_snooze_endpoint_requires_auth():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/alerts/00000000-0000-0000-0000-000000000000/snooze",
            json={"days": 7},
        )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Mark-renewed — service-level unit tests (no real DB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_renewed_sets_status_and_cancels_alerts():
    """mark_renewed() should set policy.status='renewed' and cancel pending alerts."""
    from app.services.policy_service import mark_renewed

    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    user = _make_user(tenant_id=str(tenant_id), org_id=str(org_id), role="admin")

    policy = MagicMock()
    policy.id = uuid.uuid4()
    policy.tenant_id = tenant_id
    policy.org_id = org_id
    policy.status = "active"

    # Simulate get_policy returning the policy (scope-checked)
    # and db.execute returning an empty result for the UPDATE.
    db = MagicMock()

    execute_result = MagicMock()
    db.execute = AsyncMock(return_value=execute_result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch(
        "app.services.policy_service.get_policy",
        new_callable=AsyncMock,
        return_value=policy,
    ):
        result = await mark_renewed(db, user, policy.id)

    assert result.status == "renewed"
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_renewed_propagates_not_found():
    """mark_renewed() should propagate not_found when policy is out of scope."""
    from app.core.errors import AppError
    from app.services.policy_service import mark_renewed

    user = _make_user(role="admin")
    db = MagicMock()

    with patch(
        "app.services.policy_service.get_policy",
        new_callable=AsyncMock,
        side_effect=AppError(
            __import__("app.core.errors", fromlist=["ErrorCode"]).ErrorCode.not_found,
            "Policy not found",
        ),
    ):
        with pytest.raises(AppError):
            await mark_renewed(db, user, uuid.uuid4())


# ---------------------------------------------------------------------------
# Mark-renewed — endpoint auth guard (401)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_renewed_endpoint_requires_auth():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/policies/00000000-0000-0000-0000-000000000000/mark-renewed"
        )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Escalation — dispatch_escalation writes a log row with template="escalation"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_escalation_writes_notification_log_row():
    """dispatch_escalation should write a NotificationLog row with template='escalation'."""
    from app.services.notifications.base import SendResult
    from app.services.notifications.dispatcher import dispatch_escalation

    tenant_id = uuid.uuid4()
    policy_id = uuid.uuid4()

    alert = MagicMock()
    alert.id = uuid.uuid4()
    alert.tenant_id = tenant_id
    alert.policy_id = policy_id
    alert.channel = "email"
    alert.lead_day = 7

    policy = MagicMock()
    policy.id = policy_id
    policy.title = "Factory Fire Cover"
    policy.category = "factory_property"
    policy.expiry_date = date(2026, 8, 1)

    escalation_profile = MagicMock()
    escalation_profile.email = "manager@example.com"
    escalation_profile.phone = "+919876540001"

    db = MagicMock()
    db.add = MagicMock()

    with patch(
        "app.services.notifications.email.send",
        new_callable=AsyncMock,
    ) as mock_email:
        mock_email.return_value = SendResult(status="simulated", provider_msg_id="sim-esc-1")
        await dispatch_escalation(db, alert, policy, escalation_profile)

    # A notification_log row must have been written via db.add.
    db.add.assert_called_once()
    log_row = db.add.call_args[0][0]
    assert log_row.template == "escalation"
    assert log_row.recipient == "manager@example.com"
    assert log_row.tenant_id == tenant_id


@pytest.mark.asyncio
async def test_escalation_with_no_recipient_logs_failure():
    """dispatch_escalation should log a failure row when no escalation profile is found."""
    from app.services.notifications.dispatcher import dispatch_escalation

    alert = MagicMock()
    alert.id = uuid.uuid4()
    alert.tenant_id = uuid.uuid4()
    alert.policy_id = uuid.uuid4()
    alert.channel = "email"
    alert.lead_day = 7

    policy = MagicMock()
    policy.id = alert.policy_id
    policy.title = "Vehicle Cover"
    policy.category = "vehicle"
    policy.expiry_date = date(2026, 9, 1)

    db = MagicMock()
    db.add = MagicMock()

    # Pass None as the escalation profile
    await dispatch_escalation(db, alert, policy, None)

    db.add.assert_called_once()
    log_row = db.add.call_args[0][0]
    assert log_row.template == "escalation"
    assert log_row.status == "failed"
    assert "no escalation recipient" in (log_row.error or "")


@pytest.mark.asyncio
async def test_escalation_fires_in_scan_when_escalate_true_and_lead_day_lte_7():
    """scan_and_dispatch should call dispatch_escalation when escalate=True + lead_day<=7."""
    from app.services.alert_engine import scan_and_dispatch

    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    today = date(2026, 8, 24)  # 7 days before expiry 2026-08-31

    policy = MagicMock()
    policy.id = uuid.uuid4()
    policy.tenant_id = tenant_id
    policy.org_id = org_id
    policy.title = "Factory Cover"
    policy.category = "factory_property"
    policy.expiry_date = today + timedelta(days=7)
    policy.status = "active"
    policy.owner_id = uuid.uuid4()

    rule = MagicMock()
    rule.policy_id = policy.id
    rule.tenant_id = tenant_id
    rule.lead_days = [7]
    rule.channels = ["email"]
    rule.escalate = True
    rule.is_active = True

    escalation_profile = MagicMock()
    escalation_profile.email = "manager@corp.com"
    escalation_profile.role = "manager"
    escalation_profile.is_active = True

    alert_created = MagicMock()
    alert_created.id = uuid.uuid4()
    alert_created.tenant_id = tenant_id
    alert_created.policy_id = policy.id
    alert_created.channel = "email"
    alert_created.lead_day = 7
    alert_created.status = "sent"

    # We track db.add calls to collect the Alert that was added, then patch dispatch_alert
    # to set alert.status="sent" (not acknowledged), triggering escalation.

    added_objects = []

    def fake_add(obj):
        added_objects.append(obj)
        # Mimic SQLAlchemy: if it's an Alert MagicMock, leave status as-is.

    db = MagicMock()
    db.add = MagicMock(side_effect=fake_add)
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    # scalars().all() for policies
    policies_result = MagicMock()
    policies_result.scalars.return_value.all.return_value = [policy]

    # scalars().all() for rules
    rules_result = MagicMock()
    rules_result.scalars.return_value.all.return_value = [rule]

    # .all() for existing (policy_id, lead_day, channel) tuples
    existing_result = MagicMock()
    existing_result.all.return_value = []

    # scalars().one_or_none() for escalation profile
    escalation_result = MagicMock()
    escalation_result.scalar_one_or_none.return_value = escalation_profile

    call_count = 0

    async def fake_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return policies_result
        if call_count == 2:
            return rules_result
        if call_count == 3:
            return existing_result
        # 4th call is for _find_escalation_recipient
        return escalation_result

    db.execute = fake_execute

    with patch(
        "app.services.alert_engine.dispatch_alert",
        new_callable=AsyncMock,
    ) as mock_dispatch, patch(
        "app.services.alert_engine.dispatch_escalation",
        new_callable=AsyncMock,
    ) as mock_escalation:
        # dispatch_alert sets status="sent" — not acknowledged, so escalation fires.
        async def side_dispatch(db_, alert_):
            alert_.status = "sent"

        mock_dispatch.side_effect = side_dispatch

        await scan_and_dispatch(db, today=today)

    mock_escalation.assert_awaited_once()
    # Confirm escalation was called with the escalation_profile.
    _, _, _, prof_arg = mock_escalation.call_args[0]
    assert prof_arg == escalation_profile


@pytest.mark.asyncio
async def test_escalation_does_not_fire_when_lead_day_above_threshold():
    """scan_and_dispatch should NOT call dispatch_escalation when lead_day > 7."""
    from app.services.alert_engine import scan_and_dispatch

    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    today = date(2026, 7, 2)  # 30 days before expiry

    policy = MagicMock()
    policy.id = uuid.uuid4()
    policy.tenant_id = tenant_id
    policy.org_id = org_id
    policy.title = "Stock Cover"
    policy.category = "stock_raw_material"
    policy.expiry_date = today + timedelta(days=30)
    policy.status = "active"
    policy.owner_id = uuid.uuid4()

    rule = MagicMock()
    rule.policy_id = policy.id
    rule.tenant_id = tenant_id
    rule.lead_days = [30]
    rule.channels = ["email"]
    rule.escalate = True
    rule.is_active = True

    policies_result = MagicMock()
    policies_result.scalars.return_value.all.return_value = [policy]
    rules_result = MagicMock()
    rules_result.scalars.return_value.all.return_value = [rule]
    existing_result = MagicMock()
    existing_result.all.return_value = []

    call_count = 0

    async def fake_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return policies_result
        if call_count == 2:
            return rules_result
        return existing_result

    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.execute = fake_execute

    with patch(
        "app.services.alert_engine.dispatch_alert", new_callable=AsyncMock
    ) as mock_dispatch, patch(
        "app.services.alert_engine.dispatch_escalation", new_callable=AsyncMock
    ) as mock_escalation:
        async def side_dispatch(db_, alert_):
            alert_.status = "sent"

        mock_dispatch.side_effect = side_dispatch
        await scan_and_dispatch(db, today=today)

    mock_escalation.assert_not_awaited()
