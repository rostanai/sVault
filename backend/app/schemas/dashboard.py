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
