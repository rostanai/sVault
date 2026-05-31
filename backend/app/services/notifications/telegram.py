"""Telegram Bot adapter.

Usage notes
-----------
- Telegram is cheap/free and suitable as a supplementary channel.  For primary use,
  verify reliability against your user base (not all corporate users have Telegram).
- The bot can only message users who have started a conversation with it
  (``/start`` command or inline keyboard).  The ``recipient`` here must be a Telegram
  ``chat_id`` (numeric string), not a phone number.
- To map a Profile phone/user to a Telegram chat_id you need an opt-in flow:
  the user scans a QR code or types a deeplink to start the bot, the bot captures their
  chat_id, and you store it on their Profile.  Until that mapping exists, simulated mode
  is the correct behavior.

Real-send shape
---------------
Provider: Telegram Bot API
  POST https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage
  Body: { chat_id, text, parse_mode: "HTML" }

The credential checked is ``settings.telegram_bot_token``.
"""
from __future__ import annotations

import logging
import uuid

import httpx

from app.core.config import settings
from app.services.notifications.base import SendResult

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org"


async def send(
    recipient: str,
    message: str,
    *,
    template: str | None = None,  # noqa: ARG001 — unused; kept for interface parity
) -> SendResult:
    """Send a Telegram message to ``recipient`` (chat_id as string).

    In simulated mode (no ``TELEGRAM_BOT_TOKEN`` set) logs intent and returns immediately.
    """
    if not settings.telegram_bot_token:
        logger.info(
            "telegram simulated | to=%s | message=%s",
            recipient,
            message[:120],
        )
        return SendResult(
            status="simulated",
            provider_msg_id=f"sim-telegram-{uuid.uuid4().hex[:12]}",
        )

    # --- real send ---
    url = f"{_API_BASE}/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": recipient,
        "text": message,
        "parse_mode": "HTML",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
        data = resp.json()
        if resp.status_code == 200 and data.get("ok"):
            msg_id = str(data.get("result", {}).get("message_id", ""))
            return SendResult(status="sent", provider_msg_id=msg_id or None)
        logger.warning(
            "telegram send failed | status=%d description=%s",
            resp.status_code,
            data.get("description", "unknown"),
        )
        return SendResult(
            status="failed",
            error=f"HTTP {resp.status_code}: {data.get('description', 'unknown')}",
        )
    except httpx.HTTPError as exc:
        logger.exception("telegram http error | %s", exc)
        return SendResult(status="failed", error=str(exc))
