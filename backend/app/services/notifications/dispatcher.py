"""dispatch_alert — coordinates channel selection, send, and notification_log write.

This is the integration layer called by ``alert_engine.scan_and_dispatch`` for each
due alert row.  It:

1. Resolves the recipient (policy owner's email or phone) from the alert's policy.
2. Builds the human-readable message text.
3. Calls the correct channel adapter.
4. Writes a ``notification_log`` row (idempotent: always write, even on failure).
5. Updates ``alert.status`` to ``"sent"`` or ``"failed"``.

Recipient resolution
--------------------
We fetch the Policy (already in session) and its owner's Profile.  For email the
``profile.email`` field is used; for all other channels ``profile.phone`` (E.164) is used.
Telegram requires a chat_id stored in ``profile.phone`` (or a future ``profile.telegram_id``
column) — until the mapping column exists we use ``profile.phone`` as a best-effort
fallback and log it as simulated.

If the policy has no owner, or the owner has no relevant contact, we use a placeholder
derived from the channel so the notification_log row is always written and the alert's
status is set to ``"failed"`` with a clear error.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.alerts import Alert, NotificationLog
from app.db.models.insurance import Policy
from app.db.models.tenancy import Profile
from app.services.notifications import email, sms, telegram, whatsapp
from app.services.notifications.base import SendResult

logger = logging.getLogger(__name__)

# Map channel name → adapter module.  Lookup is done through the module object
# at call-time (not at import-time) so that unit-test patches are honoured.
_ADAPTER_MODULES = {
    "whatsapp": whatsapp,
    "sms": sms,
    "telegram": telegram,
    "email": email,
}

_TEMPLATE_NAME = "renewal_reminder"
_ESCALATION_TEMPLATE = "escalation"


def _build_message(policy: Policy, lead_day: int) -> str:
    return (
        f"Reminder: insurance policy '{policy.title}' ({policy.category}) expires on "
        f"{policy.expiry_date} — {lead_day} day(s) left. Please initiate renewal."
    )


async def _resolve_recipient(
    db: AsyncSession, policy: Policy, channel: str
) -> str | None:
    """Return the best-effort contact for the policy owner on the given channel."""
    if not policy.owner_id:
        return None
    prof: Profile | None = await db.get(Profile, policy.owner_id)
    if prof is None:
        return None
    if channel == "email":
        return prof.email
    # WhatsApp, SMS, Telegram — all need a phone/contact number.
    return prof.phone


async def dispatch_alert(db: AsyncSession, alert: Alert) -> None:
    """Send the alert via its configured channel and persist the result.

    Updates ``alert.status`` in-place.  The caller is responsible for committing.

    This function never raises — all errors are captured into the NotificationLog row
    so the scan loop can continue processing other alerts.
    """
    try:
        policy: Policy | None = await db.get(Policy, alert.policy_id)
        if policy is None:
            logger.warning("dispatch_alert: policy %s not found", alert.policy_id)
            _write_log(
                db, alert, recipient=None,
                result=SendResult(status="failed", error="policy not found"),
            )
            alert.status = "failed"
            return

        recipient = await _resolve_recipient(db, policy, alert.channel)
        if not recipient:
            placeholder = f"no-recipient-{alert.channel}"
            logger.warning(
                "dispatch_alert: no recipient for policy %s channel %s",
                alert.policy_id, alert.channel,
            )
            _write_log(
                db, alert, recipient=placeholder,
                result=SendResult(
                    status="failed",
                    error="policy owner has no contact for this channel",
                ),
            )
            alert.status = "failed"
            return

        message = _build_message(policy, alert.lead_day)
        adapter_module = _ADAPTER_MODULES.get(alert.channel)
        if adapter_module is None:
            result = SendResult(status="failed", error=f"unknown channel: {alert.channel}")
        else:
            result = await adapter_module.send(recipient, message, template=_TEMPLATE_NAME)

        _write_log(db, alert, recipient=recipient, result=result)
        alert.status = "failed" if result.status == "failed" else "sent"

    except Exception as exc:  # noqa: BLE001
        # Broad catch: never crash the scan loop.
        logger.exception("dispatch_alert unexpected error for alert %s: %s", alert.id, exc)
        try:
            _write_log(
                db, alert, recipient=None,
                result=SendResult(status="failed", error=f"internal: {exc}"),
            )
        except Exception:  # noqa: BLE001
            pass
        alert.status = "failed"


def _write_log(
    db: AsyncSession,
    alert: Alert,
    recipient: str | None,
    result: SendResult,
    template: str = _TEMPLATE_NAME,
) -> None:
    """Append a NotificationLog row.  DB commit is the caller's responsibility."""
    db.add(
        NotificationLog(
            tenant_id=alert.tenant_id,
            alert_id=alert.id,
            policy_id=alert.policy_id,
            recipient=recipient,
            channel=alert.channel,
            template=template,
            status=result.status,
            provider_msg_id=result.provider_msg_id,
            error=result.error,
            sent_at=datetime.now(ZoneInfo(settings.timezone)),
        )
    )


def _build_escalation_message(policy: Policy, lead_day: int) -> str:
    return (
        f"[ESCALATION] Unacknowledged renewal alert: policy '{policy.title}' "
        f"({policy.category}) expires on {policy.expiry_date} — {lead_day} day(s) left. "
        f"No acknowledgement received; please follow up with the policy owner."
    )


async def dispatch_escalation(
    db: AsyncSession,
    alert: Alert,
    policy: Policy,
    escalation_profile: object,  # Profile | None — kept as object to avoid circular import
) -> None:
    """Send an escalation notification to the manager/admin and log it.

    Best-effort: any error is caught and logged; the caller's flow is never interrupted.
    The log row carries ``template="escalation"`` so it is distinguishable in reporting.
    Uses the email channel regardless of the alert's primary channel.
    """
    try:
        if escalation_profile is None:
            logger.debug(
                "dispatch_escalation: no manager/admin found for tenant %s",
                alert.tenant_id,
            )
            _write_log(
                db, alert, recipient=None,
                result=SendResult(
                    status="failed",
                    error="no escalation recipient found in tenant",
                ),
                template=_ESCALATION_TEMPLATE,
            )
            return

        recipient = getattr(escalation_profile, "email", None)
        if not recipient:
            _write_log(
                db, alert, recipient=None,
                result=SendResult(
                    status="failed",
                    error="escalation recipient has no email",
                ),
                template=_ESCALATION_TEMPLATE,
            )
            return

        message = _build_escalation_message(policy, alert.lead_day)
        result = await email.send(recipient, message, template=_ESCALATION_TEMPLATE)
        _write_log(db, alert, recipient=recipient, result=result, template=_ESCALATION_TEMPLATE)

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "dispatch_escalation unexpected error for alert %s: %s", alert.id, exc
        )
        try:
            _write_log(
                db, alert, recipient=None,
                result=SendResult(status="failed", error=f"internal: {exc}"),
                template=_ESCALATION_TEMPLATE,
            )
        except Exception:  # noqa: BLE001
            pass
