"""Tests for the multi-channel notification delivery layer.

Coverage:
- Each adapter returns status="simulated" with no network call when credentials are absent.
- Channel selection routes to the correct adapter.
- dispatch_alert writes a notification_log row and flips alert.status.
- notifier.send / notifier.channel_configured backward-compatibility.
"""
from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import notifier
from app.services.notifications import email, sms, telegram, whatsapp
from app.services.notifications.base import SendResult
from app.services.notifications.dispatcher import dispatch_alert

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_alert(
    channel: str = "email",
    lead_day: int = 30,
    tenant_id: uuid.UUID | None = None,
    policy_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
    alert_id: uuid.UUID | None = None,
) -> MagicMock:
    alert = MagicMock()
    alert.id = alert_id or uuid.uuid4()
    alert.tenant_id = tenant_id or uuid.uuid4()
    alert.org_id = org_id or uuid.uuid4()
    alert.policy_id = policy_id or uuid.uuid4()
    alert.channel = channel
    alert.lead_day = lead_day
    alert.status = "scheduled"
    return alert


def _make_policy(
    title: str = "Factory Fire Cover",
    category: str = "factory_property",
    expiry_date: date = date(2026, 8, 1),
    owner_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
    policy_id: uuid.UUID | None = None,
) -> MagicMock:
    policy = MagicMock()
    policy.id = policy_id or uuid.uuid4()
    policy.title = title
    policy.category = category
    policy.expiry_date = expiry_date
    policy.owner_id = owner_id or uuid.uuid4()
    policy.tenant_id = tenant_id or uuid.uuid4()
    policy.org_id = org_id or uuid.uuid4()
    return policy


def _make_profile(
    email_addr: str | None = "owner@example.com",
    phone: str | None = "+919876543210",
) -> MagicMock:
    prof = MagicMock()
    prof.email = email_addr
    prof.phone = phone
    return prof


def _make_db(policy: MagicMock | None = None, profile: MagicMock | None = None) -> MagicMock:
    """Return a fake AsyncSession with a sync ``add`` and an async ``get``."""
    db = MagicMock()

    # db.get is an async call — configure it as AsyncMock.
    async def fake_get(model_class, _pk):
        if policy is not None and model_class.__name__ == "Policy":
            return policy
        if profile is not None and model_class.__name__ == "Profile":
            return profile
        return None

    db.get = fake_get

    # db.add is synchronous in SQLAlchemy — keep it as a regular MagicMock so
    # call_args inspection works without awaiting.
    db.add = MagicMock()
    return db


# ---------------------------------------------------------------------------
# 1. Adapter simulated-mode tests (no credential → no network call)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_whatsapp_simulated_when_no_token():
    """WhatsApp adapter returns simulated and makes no HTTP call when token is absent."""
    with patch("app.services.notifications.whatsapp.settings") as mock_settings:
        mock_settings.whatsapp_token = ""
        result = await whatsapp.send("+919876543210", "Test renewal message")
    assert result.status == "simulated"
    assert result.provider_msg_id is not None
    assert result.provider_msg_id.startswith("sim-whatsapp-")
    assert result.error is None


@pytest.mark.asyncio
async def test_sms_simulated_when_no_key():
    """SMS adapter returns simulated and makes no HTTP call when api_key is absent."""
    with patch("app.services.notifications.sms.settings") as mock_settings:
        mock_settings.sms_api_key = ""
        result = await sms.send("+919876543210", "Policy expires in 7 days")
    assert result.status == "simulated"
    assert result.provider_msg_id is not None
    assert result.provider_msg_id.startswith("sim-sms-")
    assert result.error is None


@pytest.mark.asyncio
async def test_telegram_simulated_when_no_token():
    """Telegram adapter returns simulated and makes no HTTP call when bot token is absent."""
    with patch("app.services.notifications.telegram.settings") as mock_settings:
        mock_settings.telegram_bot_token = ""
        result = await telegram.send("123456789", "Policy renewal reminder")
    assert result.status == "simulated"
    assert result.provider_msg_id is not None
    assert result.provider_msg_id.startswith("sim-telegram-")
    assert result.error is None


@pytest.mark.asyncio
async def test_email_simulated_when_no_key():
    """Email adapter returns simulated and makes no HTTP call when api_key is absent."""
    with patch("app.services.notifications.email.settings") as mock_settings:
        mock_settings.email_api_key = ""
        result = await email.send("owner@example.com", "Your policy expires soon")
    assert result.status == "simulated"
    assert result.provider_msg_id is not None
    assert result.provider_msg_id.startswith("sim-email-")
    assert result.error is None


# ---------------------------------------------------------------------------
# 2. Simulated mode: no real HTTP client is instantiated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_whatsapp_makes_no_http_call_in_simulated_mode():
    with patch("app.services.notifications.whatsapp.settings") as mock_settings, \
         patch("app.services.notifications.whatsapp.httpx.AsyncClient") as mock_client:
        mock_settings.whatsapp_token = ""
        result = await whatsapp.send("+919876543210", "message")
    mock_client.assert_not_called()
    assert result.status == "simulated"


@pytest.mark.asyncio
async def test_sms_makes_no_http_call_in_simulated_mode():
    with patch("app.services.notifications.sms.settings") as mock_settings, \
         patch("app.services.notifications.sms.httpx.AsyncClient") as mock_client:
        mock_settings.sms_api_key = ""
        result = await sms.send("+919876543210", "message")
    mock_client.assert_not_called()
    assert result.status == "simulated"


@pytest.mark.asyncio
async def test_telegram_makes_no_http_call_in_simulated_mode():
    with patch("app.services.notifications.telegram.settings") as mock_settings, \
         patch("app.services.notifications.telegram.httpx.AsyncClient") as mock_client:
        mock_settings.telegram_bot_token = ""
        result = await telegram.send("12345", "message")
    mock_client.assert_not_called()
    assert result.status == "simulated"


@pytest.mark.asyncio
async def test_email_makes_no_http_call_in_simulated_mode():
    with patch("app.services.notifications.email.settings") as mock_settings, \
         patch("app.services.notifications.email.httpx.AsyncClient") as mock_client:
        mock_settings.email_api_key = ""
        result = await email.send("owner@example.com", "message")
    mock_client.assert_not_called()
    assert result.status == "simulated"


# ---------------------------------------------------------------------------
# 3. Channel selection maps correctly in notifier facade
#    Patch at the adapter module's own path so module-level lookup works.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notifier_routes_email_to_email_adapter():
    """notifier.send("email", ...) delegates to the email adapter."""
    with patch("app.services.notifications.email.send", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = SendResult(status="simulated", provider_msg_id="sim-x")
        result = await notifier.send("email", "owner@example.com", "Test")
    mock_send.assert_called_once_with("owner@example.com", "Test")
    assert result.status == "simulated"


@pytest.mark.asyncio
async def test_notifier_routes_whatsapp_to_whatsapp_adapter():
    with patch("app.services.notifications.whatsapp.send", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = SendResult(status="simulated", provider_msg_id="sim-y")
        result = await notifier.send("whatsapp", "+919876543210", "Test")
    mock_send.assert_called_once_with("+919876543210", "Test")
    assert result.status == "simulated"


@pytest.mark.asyncio
async def test_notifier_routes_sms_to_sms_adapter():
    with patch("app.services.notifications.sms.send", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = SendResult(status="simulated", provider_msg_id="sim-z")
        result = await notifier.send("sms", "+919876543210", "Test")
    mock_send.assert_called_once_with("+919876543210", "Test")
    assert result.status == "simulated"


@pytest.mark.asyncio
async def test_notifier_routes_telegram_to_telegram_adapter():
    with patch("app.services.notifications.telegram.send", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = SendResult(status="simulated", provider_msg_id="sim-t")
        result = await notifier.send("telegram", "123456", "Test")
    mock_send.assert_called_once_with("123456", "Test")
    assert result.status == "simulated"


@pytest.mark.asyncio
async def test_notifier_fails_on_no_recipient():
    result = await notifier.send("email", None, "Test")
    assert result.status == "failed"
    assert "no recipient" in (result.error or "")


@pytest.mark.asyncio
async def test_notifier_fails_on_unknown_channel():
    result = await notifier.send("carrier_pigeon", "someone", "Test")
    assert result.status == "failed"
    assert "unknown channel" in (result.error or "")


def test_notifier_channel_configured_false_without_credentials():
    """All channels should be unconfigured in test environment (no real creds)."""
    for ch in ("whatsapp", "sms", "telegram", "email"):
        assert notifier.channel_configured(ch) is False


# ---------------------------------------------------------------------------
# 4. dispatch_alert: writes notification_log and updates alert.status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_alert_writes_log_and_sets_status_sent():
    """dispatch_alert should add a NotificationLog row and set alert.status to 'sent'."""
    policy_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    policy = _make_policy(
        policy_id=policy_id, tenant_id=tenant_id, org_id=org_id, owner_id=owner_id
    )
    profile = _make_profile(email_addr="owner@example.com", phone="+919876543210")
    alert = _make_alert(
        channel="email", lead_day=30, tenant_id=tenant_id,
        policy_id=policy_id, org_id=org_id,
    )
    db = _make_db(policy=policy, profile=profile)

    with patch(
        "app.services.notifications.email.send",
        new_callable=AsyncMock,
    ) as mock_email:
        mock_email.return_value = SendResult(
            status="simulated",
            provider_msg_id="sim-email-abc123",
        )
        await dispatch_alert(db, alert)

    # NotificationLog row was added via db.add.
    db.add.assert_called_once()
    log_arg = db.add.call_args[0][0]
    assert log_arg.channel == "email"
    assert log_arg.status == "simulated"
    assert log_arg.recipient == "owner@example.com"
    assert log_arg.provider_msg_id == "sim-email-abc123"
    assert log_arg.tenant_id == tenant_id
    assert log_arg.policy_id == policy_id

    # Alert status flipped to "sent" (simulated is non-failure).
    assert alert.status == "sent"


@pytest.mark.asyncio
async def test_dispatch_alert_sets_failed_on_adapter_failure():
    """dispatch_alert sets alert.status='failed' when the adapter returns failed."""
    policy_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    policy = _make_policy(policy_id=policy_id, tenant_id=tenant_id, owner_id=owner_id)
    profile = _make_profile()
    alert = _make_alert(channel="whatsapp", lead_day=7, tenant_id=tenant_id, policy_id=policy_id)
    db = _make_db(policy=policy, profile=profile)

    with patch(
        "app.services.notifications.whatsapp.send",
        new_callable=AsyncMock,
    ) as mock_wa:
        mock_wa.return_value = SendResult(status="failed", error="timeout")
        await dispatch_alert(db, alert)

    assert alert.status == "failed"
    log_arg = db.add.call_args[0][0]
    assert log_arg.status == "failed"
    assert log_arg.error == "timeout"


@pytest.mark.asyncio
async def test_dispatch_alert_handles_missing_policy():
    """dispatch_alert logs failure and sets status='failed' when policy is not found."""
    alert = _make_alert(channel="email", lead_day=30)
    db = _make_db(policy=None, profile=None)

    await dispatch_alert(db, alert)

    assert alert.status == "failed"
    db.add.assert_called_once()
    log_arg = db.add.call_args[0][0]
    assert log_arg.status == "failed"
    assert "policy not found" in (log_arg.error or "")


@pytest.mark.asyncio
async def test_dispatch_alert_handles_no_recipient():
    """dispatch_alert sets status='failed' when the policy owner has no contact."""
    policy_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    policy = _make_policy(policy_id=policy_id, tenant_id=tenant_id, owner_id=owner_id)
    # profile with no email or phone
    profile = _make_profile(email_addr=None, phone=None)

    alert = _make_alert(channel="email", lead_day=15, tenant_id=tenant_id, policy_id=policy_id)
    db = _make_db(policy=policy, profile=profile)

    await dispatch_alert(db, alert)

    assert alert.status == "failed"
    db.add.assert_called_once()
    log_arg = db.add.call_args[0][0]
    assert log_arg.status == "failed"


@pytest.mark.asyncio
async def test_dispatch_alert_uses_phone_for_whatsapp():
    """dispatch_alert uses profile.phone (not email) as recipient for WhatsApp."""
    policy_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    policy = _make_policy(policy_id=policy_id, tenant_id=tenant_id, owner_id=owner_id)
    profile = _make_profile(email_addr="owner@example.com", phone="+919876543210")
    alert = _make_alert(channel="whatsapp", lead_day=30, tenant_id=tenant_id, policy_id=policy_id)
    db = _make_db(policy=policy, profile=profile)

    with patch(
        "app.services.notifications.whatsapp.send",
        new_callable=AsyncMock,
    ) as mock_wa:
        mock_wa.return_value = SendResult(status="simulated", provider_msg_id="sim-wa-abc")
        await dispatch_alert(db, alert)

    # Adapter was called with the phone number, not the email.
    recipient_used = mock_wa.call_args[0][0]
    assert recipient_used == "+919876543210"


@pytest.mark.asyncio
async def test_dispatch_alert_uses_email_for_email_channel():
    """dispatch_alert uses profile.email as recipient for email channel."""
    policy_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    policy = _make_policy(policy_id=policy_id, tenant_id=tenant_id, owner_id=owner_id)
    profile = _make_profile(email_addr="owner@example.com", phone="+919876543210")
    alert = _make_alert(channel="email", lead_day=7, tenant_id=tenant_id, policy_id=policy_id)
    db = _make_db(policy=policy, profile=profile)

    with patch(
        "app.services.notifications.email.send",
        new_callable=AsyncMock,
    ) as mock_email:
        mock_email.return_value = SendResult(status="simulated", provider_msg_id="sim-em-abc")
        await dispatch_alert(db, alert)

    recipient_used = mock_email.call_args[0][0]
    assert recipient_used == "owner@example.com"


# ---------------------------------------------------------------------------
# 5. SendResult dataclass
# ---------------------------------------------------------------------------

def test_send_result_defaults():
    r = SendResult(status="simulated")
    assert r.status == "simulated"
    assert r.provider_msg_id is None
    assert r.error is None


def test_send_result_full():
    r = SendResult(status="sent", provider_msg_id="msg-123", error=None)
    assert r.status == "sent"
    assert r.provider_msg_id == "msg-123"


# ---------------------------------------------------------------------------
# 6. Backward-compat: existing notifier interface still works
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_existing_notifier_send_simulated():
    """Preserve backward-compat: notifier.send returns simulated in test env."""
    res = await notifier.send("email", "test@example.com", "renewal notice")
    assert res.status == "simulated"


@pytest.mark.asyncio
async def test_existing_notifier_send_no_recipient_failed():
    """Preserve backward-compat: notifier.send with None recipient returns failed."""
    res = await notifier.send("email", None, "notice")
    assert res.status == "failed"
