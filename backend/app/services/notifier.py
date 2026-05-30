"""Pluggable multi-channel notifier.

Each channel returns (status, provider_msg_id, error). When a channel's credentials
are not configured it runs in **simulated** mode — it records the intended message in
notification_log (status='simulated') without sending. Real senders (WhatsApp BSP, SMS
DLT, Telegram, email provider) are wired in as credentials become available
(see docs/START_NOW.md). Channel fallback/escalation is handled by the engine.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings

# Which config flag gates each channel's live mode.
_CHANNEL_CRED = {
    "whatsapp": lambda: settings.whatsapp_token,
    "sms": lambda: settings.sms_api_key,
    "telegram": lambda: settings.telegram_bot_token,
    "email": lambda: settings.email_api_key,
}


@dataclass
class SendResult:
    status: str  # sent | simulated | failed | skipped
    provider_msg_id: str | None = None
    error: str | None = None


def channel_configured(channel: str) -> bool:
    cred = _CHANNEL_CRED.get(channel)
    return bool(cred and cred())


async def send(channel: str, recipient: str | None, message: str) -> SendResult:
    if not recipient:
        return SendResult("failed", error="no recipient (policy owner has no email/phone)")
    if not channel_configured(channel):
        # Not live yet — record intent so the engine + dashboard show what would send.
        return SendResult("simulated")
    # TODO(channels): real senders.
    #   whatsapp -> BSP template message API; sms -> DLT-registered gateway;
    #   telegram -> bot sendMessage; email -> transactional provider.
    # Until implemented, treat configured channels as queued for the real sender.
    return SendResult("queued")
