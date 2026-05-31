"""Pluggable multi-channel notifier — thin facade over the notifications package.

This module preserves the public interface used by ``alert_engine`` and existing tests:

  ``channel_configured(channel: str) -> bool``
  ``async send(channel, recipient, message) -> SendResult``
  ``SendResult`` dataclass

All real dispatch logic now lives in ``app.services.notifications``.  This module
re-exports ``SendResult`` and routes ``send()`` calls through the per-channel adapters so
existing callers require no changes.

See ``app/services/notifications/`` for channel-specific notes on India DLT / WhatsApp
utility-template compliance.
"""
from __future__ import annotations

from app.core.config import settings
from app.services.notifications import email, sms, telegram, whatsapp
from app.services.notifications.base import SendResult  # re-export for callers

__all__ = ["SendResult", "channel_configured", "send"]

# Which config flag gates each channel's live mode.
_CHANNEL_CRED = {
    "whatsapp": lambda: settings.whatsapp_token,
    "sms": lambda: settings.sms_api_key,
    "telegram": lambda: settings.telegram_bot_token,
    "email": lambda: settings.email_api_key,
}

# Module-level references — lookup goes through the module object at call-time
# so unit-test patches on e.g. ``whatsapp.send`` are honoured correctly.
_ADAPTER_MODULES = {
    "whatsapp": whatsapp,
    "sms": sms,
    "telegram": telegram,
    "email": email,
}


def channel_configured(channel: str) -> bool:
    """Return True if the channel has credentials configured (live mode)."""
    cred = _CHANNEL_CRED.get(channel)
    return bool(cred and cred())


async def send(channel: str, recipient: str | None, message: str) -> SendResult:
    """Send ``message`` via ``channel`` to ``recipient``.

    Returns a ``SendResult`` with status ``"simulated"``, ``"sent"``, or ``"failed"``.
    When the channel credential is absent the adapter returns ``"simulated"`` without
    making any network call.
    """
    if not recipient:
        return SendResult("failed", error="no recipient (policy owner has no email/phone)")
    adapter_mod = _ADAPTER_MODULES.get(channel)
    if adapter_mod is None:
        return SendResult("failed", error=f"unknown channel: {channel}")
    return await adapter_mod.send(recipient, message)
