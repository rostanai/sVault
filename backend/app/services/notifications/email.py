"""Email adapter — transactional email via HTTP provider.

Transactional email notes
-------------------------
- Use a transactional provider (SendGrid, Amazon SES, Resend, Postmark) rather than SMTP
  for better deliverability and bounce handling.
- For India compliance, ensure the sender domain has SPF/DKIM/DMARC records configured.
- Policy documents can be attached to emails; the base adapter sends text only.
  Attach PDFs when the caller passes an ``attachments`` kwarg in a future extension.

Real-send shape
---------------
This adapter targets the **Resend** HTTP API (https://resend.com) as a representative
transactional provider.  The API is simple and idiomatic:

  POST https://api.resend.com/emails
  Authorization: Bearer {EMAIL_API_KEY}
  Body: { from, to, subject, html }

To switch to SendGrid or Amazon SES, change the URL and body shape in the real-send block.
The credential checked is ``settings.email_api_key``.
Additional env vars for live mode (add to config.py):
  EMAIL_FROM_ADDRESS — verified sender address (e.g. alerts@svault.example.com)
"""
from __future__ import annotations

import logging
import uuid

import httpx

from app.core.config import settings
from app.services.notifications.base import SendResult

logger = logging.getLogger(__name__)

_RESEND_API_URL = "https://api.resend.com/emails"
_DEFAULT_FROM = "sVault Alerts <alerts@svault.example.com>"
_DEFAULT_SUBJECT = "Insurance Renewal Reminder — sVault"


async def send(
    recipient: str,
    message: str,
    *,
    template: str | None = None,  # noqa: ARG001 — unused; kept for interface parity
) -> SendResult:
    """Send a transactional email to ``recipient`` (email address).

    In simulated mode (no ``EMAIL_API_KEY`` set) logs intent and returns immediately.
    In live mode sends via the Resend API.
    """
    if not settings.email_api_key:
        logger.info(
            "email simulated | to=%s | message=%s",
            recipient,
            message[:120],
        )
        return SendResult(
            status="simulated",
            provider_msg_id=f"sim-email-{uuid.uuid4().hex[:12]}",
        )

    # --- real send ---
    from_addr = getattr(settings, "email_from_address", _DEFAULT_FROM)

    # Build a minimal HTML body from the plain-text message.
    html_body = (
        f"<p>{message}</p>"
        f"<hr/><p style='font-size:12px;color:#888'>sVault — Corporate Insurance Portal</p>"
    )

    payload = {
        "from": from_addr,
        "to": [recipient],
        "subject": _DEFAULT_SUBJECT,
        "html": html_body,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                _RESEND_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {settings.email_api_key}"},
            )
        if resp.status_code in (200, 201):
            data = resp.json()
            return SendResult(status="sent", provider_msg_id=data.get("id"))
        logger.warning("email send failed | status=%d", resp.status_code)
        return SendResult(status="failed", error=f"HTTP {resp.status_code}")
    except httpx.HTTPError as exc:
        logger.exception("email http error | %s", exc)
        return SendResult(status="failed", error=str(exc))
