"""Dashboard aggregation — tenant/org-scoped (RLS also enforces in the DB)."""
from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.db.models import Organization, Policy
from app.schemas.dashboard import GroupDashboardResponse, OrgRollup, Totals
from app.services.alert_engine import ALERTABLE_STATUSES, today_in_tz
from app.services.policy_service import _accessible_org_filter, _owner_filter


def _scoped(stmt, user: CurrentUser):
    stmt = stmt.where(Policy.tenant_id == uuid.UUID(user.tenant_id))
    org = _accessible_org_filter(user)
    if org is not None:
        stmt = stmt.where(Policy.org_id == org)
    # Object-level: an owner's aggregates cover only the policies they own.
    if (oid := _owner_filter(user)) is not None:
        stmt = stmt.where(Policy.owner_id == oid)
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


async def get_group_dashboard(
    db: AsyncSession, user: CurrentUser
) -> GroupDashboardResponse:
    """Return group-wide totals + a per-org breakdown for all accessible orgs.

    Only orgs that have at least one policy visible to the caller appear in
    ``by_org``.  Orgs with zero policies are intentionally excluded: it keeps
    the query to a single grouped pass on ``policies`` (no left join to
    ``organizations`` needed for the count columns) and avoids leaking org
    names for shells that have no insurance data.  Org names are resolved in
    one additional query after the aggregation.

    Results are ordered by ``premium_inr`` descending then ``org_name``
    ascending so high-value subsidiaries appear first.

    Decimal monetary values are serialised as fixed-point strings
    (``str(Decimal("1234567.89"))`` → ``"1234567.89"``) to avoid JSON
    floating-point drift.
    """
    today = today_in_tz()
    in_30 = today + timedelta(days=30)

    tenant_uuid = uuid.UUID(user.tenant_id)
    accessible_org: uuid.UUID | None = _accessible_org_filter(user)

    # --- Group-wide totals (reuse existing _scoped helper) ---
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

    status_counts_rows = (
        await db.execute(
            _scoped(select(Policy.status, func.count()), user).group_by(Policy.status)
        )
    ).all()
    lapsed_count = {s: c for s, c in status_counts_rows}.get("lapsed", 0)

    totals = Totals(
        policies=total_count,
        sum_insured_inr=total_si,
        premium_inr=total_prem,
        lapsed=lapsed_count,
    )

    # --- Per-org grouped aggregation (single query) ---
    # Count policies expiring within the next 30 days and in an alertable status
    # using a conditional aggregate (standard SQL FILTER clause via SQLAlchemy
    # func.count with a where clause isn't directly supported; use case instead).
    from sqlalchemy import case  # noqa: PLC0415 — local import keeps top-level clean

    expiring_30_expr = func.count(
        case(
            (
                (Policy.expiry_date >= today)
                & (Policy.expiry_date <= in_30)
                & Policy.status.in_(ALERTABLE_STATUSES),
                Policy.id,
            ),
            else_=None,
        )
    )

    agg_stmt = (
        select(
            Policy.org_id,
            func.count(Policy.id).label("policies"),
            func.coalesce(func.sum(Policy.sum_insured_inr), 0).label("sum_insured_inr"),
            func.coalesce(func.sum(Policy.premium_inr), 0).label("premium_inr"),
            expiring_30_expr.label("expiring_30"),
        )
        .where(Policy.tenant_id == tenant_uuid)
        .group_by(Policy.org_id)
    )
    if accessible_org is not None:
        agg_stmt = agg_stmt.where(Policy.org_id == accessible_org)
    # Object-level: for an owner the per-org rollup collapses to only their own
    # policies (within their own org).
    if (owner_oid := _owner_filter(user)) is not None:
        agg_stmt = agg_stmt.where(Policy.owner_id == owner_oid)

    agg_rows = (await db.execute(agg_stmt)).all()

    if not agg_rows:
        return GroupDashboardResponse(totals=totals, by_org=[])

    # --- Resolve org names in one lookup ---
    org_ids = [row.org_id for row in agg_rows]
    org_name_map: dict[uuid.UUID, str] = {}
    org_rows = (
        await db.execute(
            select(Organization.id, Organization.name).where(
                Organization.id.in_(org_ids)
            )
        )
    ).all()
    for org_id, org_name in org_rows:
        org_name_map[org_id] = org_name

    # --- Build OrgRollup list, ordered by premium desc then name asc ---
    rollups = [
        OrgRollup(
            org_id=row.org_id,
            org_name=org_name_map.get(row.org_id, str(row.org_id)),
            policies=row.policies,
            sum_insured_inr=str(row.sum_insured_inr),
            premium_inr=str(row.premium_inr),
            expiring_30=row.expiring_30,
        )
        for row in agg_rows
    ]
    rollups.sort(key=lambda r: (-float(r.premium_inr), r.org_name))

    return GroupDashboardResponse(totals=totals, by_org=rollups)
