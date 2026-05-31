"""Email adapter — transactional email via SMTP or HTTP provider.

Transactional email notes
-------------------------
- SMTP (any server: Gmail, your host, Amazon SES SMTP) is used when ``SMTP_HOST``
  is set. Otherwise the Resend HTTP API is used when ``EMAIL_API_KEY`` is set.
  With neither configured the adapter runs in simulated mode (logs intent only).
- For India compliance, ensure the sender domain has SPF/DKIM/DMARC records configured.
- Policy documents can be attached to emails; the base adapter sends text only.

Resend HTTP fallback shape
--------------------------
  POST https://api.resend.com/emails
  Authorization: Bearer {EMAIL_API_KEY}
  Body: { from, to, subject, html }

The SMTP credentials checked are ``settings.smtp_host`` / ``smtp_port`` /
``smtp_username`` / ``smtp_password`` / ``smtp_from`` / ``smtp_starttls``.
The Resend credential checked is ``settings.email_api_key``.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
import uuid
from email.message import EmailMessage

import httpx

from app.core.config import settings
from app.services.notifications.base import SendResult

logger = logging.getLogger(__name__)

_RESEND_API_URL = "https://api.resend.com/emails"
_DEFAULT_FROM = "sVault Alerts <alerts@svault.example.com>"
_DEFAULT_SUBJECT = "Insurance Renewal Reminder — sVault"


def _send_smtp_sync(recipient: str, subject: str, message: str) -> SendResult:
    """Blocking SMTP send (run via asyncio.to_thread). STARTTLS (587) or SSL (465)."""
    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_username
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(message)
    msg.add_alternative(
        f"<p>{message}</p><hr/>"
        f"<p style='font-size:12px;color:#888'>sVault — Corporate Insurance Portal</p>",
        subtype="html",
    )
    ctx = ssl.create_default_context()
    try:
        if settings.smtp_starttls:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
                s.starttls(context=ctx)
                if settings.smtp_username:
                    s.login(settings.smtp_username, settings.smtp_password)
                s.send_message(msg)
        else:  # implicit SSL (typically port 465)
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=15, context=ctx
            ) as s:
                if settings.smtp_username:
                    s.login(settings.smtp_username, settings.smtp_password)
                s.send_message(msg)
        return SendResult(status="sent", provider_msg_id=f"smtp-{uuid.uuid4().hex[:12]}")
    except Exception as exc:  # smtplib raises a variety of exceptions
        logger.warning("email smtp send failed | %s", exc)
        return SendResult(status="failed", error=str(exc))


async def send(
    recipient: str,
    message: str,
    *,
    template: str | None = None,  # noqa: ARG001 — unused; kept for interface parity
) -> SendResult:
    """Send a transactional email to ``recipient`` (email address).

    Transport priority: **SMTP** (when ``SMTP_HOST`` set) → **Resend** HTTP API
    (when ``EMAIL_API_KEY`` set) → **simulated** (logs intent, no real send).
    """
    if settings.smtp_host:
        return await asyncio.to_thread(
            _send_smtp_sync, recipient, _DEFAULT_SUBJECT, message
        )

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

    # --- real send (Resend HTTP) ---
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
