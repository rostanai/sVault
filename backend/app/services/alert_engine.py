"""Renewal alert engine — the core differentiator.

Daily scan (triggered by pg_cron / Vercel Cron on serverless) finds policies whose
expiry is exactly `lead_day` days away (computed in IST), schedules an alert per
(policy, lead_day, channel), dispatches via the notifier, and logs delivery.
Idempotent: the unique (policy_id, lead_day, channel) constraint means each reminder
fires at most once, ever.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Alert, AlertRule, NotificationLog, Policy, Profile
from app.services import notifier

DEFAULT_LEAD_DAYS = [60, 30, 15, 7, 1]
DEFAULT_CHANNELS = ["whatsapp", "email"]
ALERTABLE_STATUSES = ("active", "expiring")


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

                recipient = await _recipient(db, p, ch)
                result = await notifier.send(ch, recipient, build_message(p, d))
                db.add(NotificationLog(
                    tenant_id=p.tenant_id, alert_id=alert.id, policy_id=p.id,
                    recipient=recipient, channel=ch, template="renewal_reminder",
                    status=result.status, provider_msg_id=result.provider_msg_id,
                    error=result.error,
                ))
                alert.status = "failed" if result.status == "failed" else "sent"
                dispatched += 1
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
