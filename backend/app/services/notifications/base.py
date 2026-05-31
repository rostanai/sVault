"""Base types shared across all channel adapters.

Every channel adapter exposes:

    async def send(
        recipient: str,
        message: str,
        *,
        template: str | None = None,
    ) -> SendResult

SendResult is a small dataclass that the dispatcher and NotificationLog consumer read.

Simulated mode
--------------
When the channel's credential (pulled from ``app.core.config.settings``) is an empty
string the adapter MUST return ``status="simulated"`` without making any network call.
This lets the full dispatch path run end-to-end in dev / CI with no real provider keys.

Real-send shape
---------------
When credentials ARE set the adapter should use ``httpx.AsyncClient`` and wrap all
errors into a ``status="failed"`` result.  The real-send code will not run without
keys so we keep it minimal but structurally correct.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SendResult:
    """Return value from every channel adapter's ``send()`` function."""

    status: str  # "sent" | "simulated" | "failed" | "skipped"
    provider_msg_id: str | None = None
    error: str | None = None
