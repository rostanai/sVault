"""SMS adapter — India TRAI DLT compliant.

India TRAI DLT compliance notes (mandatory)
--------------------------------------------
1. **Entity registration**: The sending company must be registered as a "Principal Entity"
   on a DLT portal (e.g. Jio Trueconnect, Airtel, Vi, TRAI portal).  Registration is free
   but takes 1–3 business days.

2. **Template registration**: Every distinct message template must be registered BEFORE use.
   Template variables (e.g. policy name, expiry date) are marked as ``{#var#}`` in the DLT
   template.  Registration is free.

3. **Transactional/Service category**: Renewal reminders qualify as transactional/service
   messages (not promotional) because they inform about an existing customer relationship.
   Transactional messages bypass DND lists and can be delivered 24/7; promotional messages
   are restricted to 10:00–21:00 IST and are silently dropped outside that window.

4. **CTA URLs**: Any URL / app link in an SMS must be pre-whitelisted on the DLT portal
   (Aug/Oct 2024 TRAI rule).  Avoid URLs in the default template; if added, whitelist first.

5. **Sender ID**: The 6-character alphanumeric Sender ID (e.g. SVAULT) must be registered
   on the DLT portal and linked to the template.

6. **DLT template variable format**: Variables in the registered template look like
   ``{#var#}``.  When sending, replace them with actual values.  The gateway (MSG91,
   Exotel, Kaleyra, etc.) maps ``{#var#}`` slots to the parameters you supply via their API.

Recommended gateway: MSG91 (widely used, DLT-compliant, good uptime in India).

Real-send shape
---------------
Provider: MSG91 Send SMS API
  POST https://api.msg91.com/api/v5/flow
  authkey: {SMS_API_KEY}   (query param or header — MSG91 accepts both)
  Body: JSON with template_id, recipients, variables

The credential checked is ``settings.sms_api_key``.
Additional env vars for live mode (add to config.py):
  SMS_SENDER_ID   — 6-char alphanumeric registered sender (e.g. SVAULT)
  SMS_DLT_TEMPLATE_ID — DLT-registered template ID from the portal
"""
from __future__ import annotations

import logging
import uuid

import httpx

from app.core.config import settings
from app.services.notifications.base import SendResult

logger = logging.getLogger(__name__)

# Default DLT template — register this text on TRAI portal before going live.
# DLT template text (example, adapt to match your registered template exactly):
#   "Dear Customer, Your insurance policy {#var#} expires on {#var#} ({#var#} days left).
#    Please initiate renewal. - sVault"
_DLT_TEMPLATE_ID_ENV = "SMS_DLT_TEMPLATE_ID"


async def send(
    recipient: str,
    message: str,
    *,
    template: str | None = None,
) -> SendResult:
    """Send a transactional SMS to ``recipient`` (E.164, e.g. +919876543210).

    In simulated mode (no ``SMS_API_KEY`` set) logs intent and returns immediately.
    In live mode sends via MSG91 Flow API using the DLT-registered template.
    """
    if not settings.sms_api_key:
        logger.info(
            "sms simulated | to=%s | message=%s",
            recipient,
            message[:120],
        )
        return SendResult(
            status="simulated",
            provider_msg_id=f"sim-sms-{uuid.uuid4().hex[:12]}",
        )

    # --- real send ---
    sender_id = getattr(settings, "sms_sender_id", "SVAULT")
    dlt_template_id = getattr(settings, "sms_dlt_template_id", "")
    if not dlt_template_id:
        return SendResult(
            status="failed",
            error="SMS_DLT_TEMPLATE_ID not configured (required for TRAI DLT compliance)",
        )

    # Strip the country prefix if MSG91 expects 10-digit mobile (depends on gateway).
    # For MSG91 v5 flow API, the mobile should include country code without '+'.
    mobile = recipient.lstrip("+")

    payload = {
        "template_id": dlt_template_id,
        "sender": sender_id,
        "short_url": "0",
        "realTimeResponse": "1",
        "recipients": [
            {
                "mobiles": mobile,
                # Variables map to {#var#} slots in the registered DLT template.
                # The full message is passed as a single variable here; adjust if the
                # registered template has multiple named variables.
                "var": message,
            }
        ],
    }
    url = "https://api.msg91.com/api/v5/flow"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "authkey": settings.sms_api_key,
                    "content-type": "application/json",
                },
            )
        data = resp.json()
        if resp.status_code == 200 and data.get("type") == "success":
            return SendResult(
                status="sent",
                provider_msg_id=data.get("request_id"),
            )
        logger.warning("sms send failed | status=%d body=%s", resp.status_code, data)
        return SendResult(
            status="failed",
            error=f"HTTP {resp.status_code}: {data.get('message', 'unknown')}",
        )
    except httpx.HTTPError as exc:
        logger.exception("sms http error | %s", exc)
        return SendResult(status="failed", error=str(exc))
