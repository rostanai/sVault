"""Multi-channel notification delivery package.

Public API
----------
``dispatch_alert(db, alert)`` — the top-level coordinator used by the alert engine.

Channel adapters live in the sub-modules:
  whatsapp.py   — WhatsApp Business Cloud API (utility template)
  sms.py        — India TRAI DLT transactional SMS (MSG91)
  telegram.py   — Telegram Bot sendMessage
  email.py      — Transactional email (Resend-style HTTP API)

Each adapter exposes:
  ``async def send(recipient, message, *, template=None) -> SendResult``
"""
from app.services.notifications.base import SendResult
from app.services.notifications.dispatcher import dispatch_alert

__all__ = ["dispatch_alert", "SendResult"]
