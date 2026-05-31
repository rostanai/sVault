"""Renewal alert engine — the core differentiator.

Daily scan (triggered by pg_cron / Vercel Cron on serverless) finds policies whose
expiry is exactly `lead_day` days away (computed in IST), schedules an alert per
(policy, lead_day, channel), dispatches via the notifier, and logs delivery.
Idempotent: the unique (policy_id, lead_day, channel) constraint means each reminder
fires at most once, ever.

Channel delivery is handled by ``app.services.notifications.dispatcher.dispatch_alert``
which picks the right adapter (WhatsApp / SMS / Telegram / email), sends in simulated
mode when credentials are absent, and always writes a ``notification_log`` row.

Escalation rule
---------------
When ``AlertRule.escalate`` is True **and** the alert's ``lead_day <= 7`` (i.e., the
final 7-day / 1-day reminders) **and** the alert is *not already acknowledged*
(``alert.status != 'acknowledged'``), the engine also sends an escalation notification
to a manager- or admin-level user in the same tenant.  The escalation is best-effort:
it never blocks the main delivery and any failure is silently logged with
``template="escalation"`` in ``notification_log``.  Escalation uses the *email* channel
regardless of the alert's primary channel (because managers/admins are reliably reachable
by email in the test environment; the adapter falls back to simulated when unconfigured).
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Alert, AlertRule, Policy, Profile
from app.services.notifications.dispatcher import dispatch_alert, dispatch_escalation

DEFAULT_LEAD_DAYS = [60, 30, 15, 7, 1]
DEFAULT_CHANNELS = ["whatsapp", "email"]
ALERTABLE_STATUSES = ("active", "expiring")
ESCALATION_LEAD_THRESHOLD = 7  # fire escalation when lead_day <= this value

logger = logging.getLogger(__name__)


def today_in_tz() -> date:
    return datetime.now(ZoneInfo(settings.timezone)).date()


def due_lead_days(expiry: date, today: date, lead_days: list[int]) -> list[int]:
    """Lead days for which `today` is exactly that many days before expiry."""
    return [d for d in lead_days if expiry - timedelta(days=d) == today]


def resolve_rule(
    per_policy: AlertRule | None, tenant_default: AlertRule | None
) -> tuple[list[int], list[str]]:
    rule = per_policy or tenant_default
    if rule is None:
        return DEFAULT_LEAD_DAYS, DEFAULT_CHANNELS
    return (rule.lead_days or DEFAULT_LEAD_DAYS), (rule.channels or DEFAULT_CHANNELS)


def build_message(policy: Policy, lead_day: int) -> str:
    return (
        f"Reminder: insurance policy '{policy.title}' ({policy.category}) expires on "
        f"{policy.expiry_date} — {lead_day} day(s) left. Please initiate renewal."
    )


async def _recipient(db: AsyncSession, policy: Policy, channel: str) -> str | None:
    if not policy.owner_id:
        return None
    prof = await db.get(Profile, policy.owner_id)
    if prof is None:
        return None
    return prof.email if channel == "email" else prof.phone


async def _find_escalation_recipient(db: AsyncSession, tenant_id: uuid.UUID) -> Profile | None:
    """Return a manager or admin profile for the given tenant (first found)."""
    stmt = (
        select(Profile)
        .where(
            Profile.tenant_id == tenant_id,
            Profile.role.in_(["manager", "admin"]),
            Profile.is_active.is_(True),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def scan_and_dispatch(db: AsyncSession, today: date | None = None) -> dict:
    today = today or today_in_tz()

    policies = (
        await db.execute(
            select(Policy).where(
                Policy.expiry_date.is_not(None),
                Policy.status.in_(ALERTABLE_STATUSES),
            )
        )
    ).scalars().all()

    rules = (
        await db.execute(select(AlertRule).where(AlertRule.is_active.is_(True)))
    ).scalars().all()
    per_policy = {r.policy_id: r for r in rules if r.policy_id}
    tenant_default = {r.tenant_id: r for r in rules if r.policy_id is None}

    # Existing (policy, lead_day, channel) keys => idempotency without relying on errors.
    existing = {
        (a.policy_id, a.lead_day, a.channel)
        for a in (
            await db.execute(select(Alert.policy_id, Alert.lead_day, Alert.channel))
        ).all()
    }

    created = dispatched = 0
    for p in policies:
        rule = per_policy.get(p.id) or tenant_default.get(p.tenant_id)
        lead_days, channels = resolve_rule(
            per_policy.get(p.id), tenant_default.get(p.tenant_id)
        )
        for d in due_lead_days(p.expiry_date, today, lead_days):
            for ch in channels:
                key = (p.id, d, ch)
                if key in existing:
                    continue
                existing.add(key)
                alert = Alert(
                    tenant_id=p.tenant_id, org_id=p.org_id, policy_id=p.id,
                    channel=ch, lead_day=d, scheduled_for=today, status="scheduled",
                )
                db.add(alert)
                await db.flush()
                created += 1

                # dispatch_alert resolves recipient, calls the channel adapter,
                # writes a notification_log row, and updates alert.status.
                await dispatch_alert(db, alert)
                dispatched += 1

                # Fire webhook event — best-effort; never block the engine.
                try:
                    from app.services import webhook_service  # lazy import avoids cycles

                    await webhook_service.deliver(
                        db,
                        p.tenant_id,
                        "renewal.due",
                        {
                            "policy_id": str(p.id),
                            "lead_day": d,
                            "scheduled_for": str(today),
                        },
                    )
                except Exception:  # noqa: BLE001
                    pass

                # Escalation: when the rule says escalate=True AND this is a final
                # reminder (lead_day <= ESCALATION_LEAD_THRESHOLD) AND the alert was
                # not already acknowledged, also notify a manager/admin in the tenant.
                should_escalate = (
                    rule is not None and getattr(rule, "escalate", False)
                    and d <= ESCALATION_LEAD_THRESHOLD
                    and alert.status != "acknowledged"
                )
                if should_escalate:
                    escalation_recipient = await _find_escalation_recipient(
                        db, p.tenant_id
                    )
                    await dispatch_escalation(db, alert, p, escalation_recipient)

    await db.commit()
    return {"date": str(today), "alerts_created": created, "dispatched": dispatched}


async def acknowledge(db: AsyncSession, user_id: str, alert_id: uuid.UUID) -> Alert | None:
    alert = await db.get(Alert, alert_id)
    if alert is None:
        return None
    alert.status = "acknowledged"
    alert.acknowledged_by = uuid.UUID(user_id)
    alert.acknowledged_at = datetime.now(ZoneInfo(settings.timezone))
    await db.commit()
    return alert


async def snooze(
    db: AsyncSession,
    user: object,  # CurrentUser — imported lazily to avoid circular dependency
    alert_id: uuid.UUID,
    days: int,
) -> Alert | None:
    """Push alert's scheduled_for forward by `days` and reset status to 'scheduled'.

    Returns None if the alert does not exist or is outside the caller's tenant scope.
    The caller (endpoint) is responsible for raising not_found on None.
    """
    alert = await db.get(Alert, alert_id)
    if alert is None:
        return None
    # Tenant scope guard — treat cross-tenant access as not-found (never reveal existence).
    if str(alert.tenant_id) != str(user.tenant_id):  # type: ignore[attr-defined]
        return None
    alert.scheduled_for = alert.scheduled_for + timedelta(days=days)
    alert.status = "scheduled"
    # Clear previous acknowledgement so the alert re-enters the pending queue.
    alert.acknowledged_by = None
    alert.acknowledged_at = None
    await db.commit()
    await db.refresh(alert)
    return alert
