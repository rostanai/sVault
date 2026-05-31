"""Dashboard schemas (M3)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class Totals(BaseModel):
    policies: int
    sum_insured_inr: Decimal
    premium_inr: Decimal
    lapsed: int


class ExpiringBuckets(BaseModel):
    next_30: int
    next_60: int
    next_90: int


class CategoryCount(BaseModel):
    category: str
    count: int


class UpcomingPolicy(BaseModel):
    id: uuid.UUID
    title: str
    category: str
    expiry_date: date | None
    status: str
    days_left: int | None


class DashboardResponse(BaseModel):
    totals: Totals
    status_counts: dict[str, int]
    expiring: ExpiringBuckets
    by_category: list[CategoryCount]
    upcoming: list[UpcomingPolicy]


# ---- Group / consolidated dashboard ----

class OrgRollup(BaseModel):
    """Per-org aggregated row in the group dashboard.

    ``sum_insured_inr`` and ``premium_inr`` are returned as strings (formatted
    decimal) so that JSON consumers receive exact numeric text without floating-
    point representation errors.  ``expiring_30`` counts policies whose expiry
    falls within the next 30 calendar days and whose status is alertable.
    """

    org_id: uuid.UUID
    org_name: str
    policies: int
    sum_insured_inr: str
    premium_inr: str
    expiring_30: int


class GroupDashboardResponse(BaseModel):
    """Consolidated group-wide dashboard: totals + per-org breakdown.

    ``totals`` is the same shape as the single-org dashboard (reuses ``Totals``).
    ``by_org`` contains one entry per org that has at least one policy visible to
    the caller; orgs with zero policies are omitted (see service docstring).
    Results are ordered by ``premium_inr`` descending then ``org_name`` ascending.
    """

    totals: Totals
    by_org: list[OrgRollup]
