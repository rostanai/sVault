"""WhatsApp Business Cloud API adapter.

India / compliance notes
------------------------
- WhatsApp renewal reminders should use the **utility** template category (not marketing).
  Utility templates are NOT subject to promotional opt-in and attract lower Meta pricing
  than marketing templates.
- Each template must be pre-approved in Meta Business Manager before first send.
  Template name convention: ``svault_renewal_reminder`` (utility).
- Variables in the template body correspond positionally to the ``components[].parameters``
  list you send in the API call; we pass the rendered ``message`` text as the first
  (and only) body parameter so the template body is ``{{1}}``.
- Opt-in: the recipient must have opted in to receive WhatsApp messages; verify before
  sending from your own database.

Real-send shape
---------------
Provider: Meta WhatsApp Cloud API
  POST https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages
  Authorization: Bearer {WHATSAPP_TOKEN}
  Body: JSON — see https://developers.facebook.com/docs/whatsapp/cloud-api/messages/template-messages

The credential checked is ``settings.whatsapp_token`` (non-empty = live mode).
The phone-number-id is expected in the environment variable ``WHATSAPP_PHONE_NUMBER_ID``
(add to ``app/core/config.py`` when going live; not read here in simulated mode).
"""
from __future__ import annotations

import logging
import uuid

import httpx

from app.core.config import settings
from app.services.notifications.base import SendResult

logger = logging.getLogger(__name__)

# Meta Graph API version pinned — bump when Meta deprecates it.
_GRAPH_API_VERSION = "v19.0"
_TEMPLATE_NAME = "svault_renewal_reminder"
_TEMPLATE_LANGUAGE = "en"


async def send(
    recipient: str,
    message: str,
    *,
    template: str | None = None,
) -> SendResult:
    """Send a WhatsApp message to ``recipient`` (E.164 phone number, e.g. +919876543210).

    In simulated mode (no ``WHATSAPP_TOKEN`` set) logs intent and returns immediately.
    """
    if not settings.whatsapp_token:
        logger.info(
            "whatsapp simulated | to=%s | message=%s",
            recipient,
            message[:120],
        )
        return SendResult(
            status="simulated",
            provider_msg_id=f"sim-whatsapp-{uuid.uuid4().hex[:12]}",
        )

    # --- real send ---
    # WHATSAPP_PHONE_NUMBER_ID must be set in the environment (alongside WHATSAPP_TOKEN).
    phone_number_id = getattr(settings, "whatsapp_phone_number_id", "")
    if not phone_number_id:
        return SendResult(
            status="failed",
            error="WHATSAPP_PHONE_NUMBER_ID not configured",
        )

    url = f"https://graph.facebook.com/{_GRAPH_API_VERSION}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "template",
        "template": {
            "name": template or _TEMPLATE_NAME,
            "language": {"code": _TEMPLATE_LANGUAGE},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": message}],
                }
            ],
        },
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
            )
        if resp.status_code == 200:
            data = resp.json()
            msg_id = (
                data.get("messages", [{}])[0].get("id")
                if data.get("messages")
                else None
            )
            return SendResult(status="sent", provider_msg_id=msg_id)
        logger.warning("whatsapp send failed | status=%d", resp.status_code)
        return SendResult(status="failed", error=f"HTTP {resp.status_code}")
    except httpx.HTTPError as exc:
        logger.exception("whatsapp http error | %s", exc)
        return SendResult(status="failed", error=str(exc))
