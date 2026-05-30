"""Dashboard aggregation — tenant/org-scoped (RLS also enforces in the DB)."""
from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.db.models import Policy
from app.services.alert_engine import ALERTABLE_STATUSES, today_in_tz
from app.services.policy_service import _accessible_org_filter


def _scoped(stmt, user: CurrentUser):
    stmt = stmt.where(Policy.tenant_id == uuid.UUID(user.tenant_id))
    org = _accessible_org_filter(user)
    if org is not None:
        stmt = stmt.where(Policy.org_id == org)
    return stmt


async def get_dashboard(db: AsyncSession, user: CurrentUser) -> dict:
    today = today_in_tz()

    total_count, total_si, total_prem = (
        await db.execute(
            _scoped(
                select(
                    func.count(Policy.id),
                    func.coalesce(func.sum(Policy.sum_insured_inr), 0),
                    func.coalesce(func.sum(Policy.premium_inr), 0),
                ),
                user,
            )
        )
    ).one()

    status_counts = {
        s: c
        for s, c in (
            await db.execute(
                _scoped(select(Policy.status, func.count()), user).group_by(Policy.status)
            )
        ).all()
    }

    by_category = [
        {"category": c, "count": n}
        for c, n in (
            await db.execute(
                _scoped(select(Policy.category, func.count()), user).group_by(Policy.category)
            )
        ).all()
    ]

    async def _bucket(days: int) -> int:
        stmt = _scoped(select(func.count(Policy.id)), user).where(
            Policy.expiry_date >= today,
            Policy.expiry_date <= today + timedelta(days=days),
            Policy.status.in_(ALERTABLE_STATUSES),
        )
        return (await db.execute(stmt)).scalar_one()

    expiring = {"next_30": await _bucket(30), "next_60": await _bucket(60),
                "next_90": await _bucket(90)}

    upcoming_rows = (
        await db.execute(
            _scoped(select(Policy), user)
            .where(Policy.expiry_date >= today)
            .order_by(Policy.expiry_date.asc())
            .limit(10)
        )
    ).scalars().all()
    upcoming = [
        {
            "id": p.id, "title": p.title, "category": p.category,
            "expiry_date": p.expiry_date, "status": p.status,
            "days_left": (p.expiry_date - today).days if p.expiry_date else None,
        }
        for p in upcoming_rows
    ]

    return {
        "totals": {
            "policies": total_count, "sum_insured_inr": total_si,
            "premium_inr": total_prem, "lapsed": status_counts.get("lapsed", 0),
        },
        "status_counts": status_counts,
        "expiring": expiring,
        "by_category": by_category,
        "upcoming": upcoming,
    }
