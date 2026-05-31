"""Schemas for renewal reporting (data-io feature)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class RenewalReportRow(BaseModel):
    """One row in the renewal-due report."""

    policy_id: uuid.UUID
    title: str
    category: str
    provider_name: str | None
    expiry_date: date | None
    days_left: int | None
    premium_inr: Decimal | None
    sum_insured_inr: Decimal | None
    status: str


class ImportResult(BaseModel):
    """Summary returned by the bulk-import endpoint."""

    created: int
    skipped: int
    errors: list[ImportRowError]


class ImportRowError(BaseModel):
    row: int
    message: str
