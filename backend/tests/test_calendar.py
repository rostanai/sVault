"""Tests for the iCalendar renewal-feed endpoint and calendar_service.build_ics.

Coverage
--------
1. Auth guard — GET /api/v1/calendar.ics without a token → 401.
2. build_ics unit tests:
   a. Empty policy list → valid VCALENDAR with no VEVENT blocks.
   b. Policy without expiry_date → no VEVENT emitted.
   c. Policy with expiry_date only → one VEVENT (expiry), correct UID, DTSTART;VALUE=DATE.
   d. Policy with expiry_date + renewal_date → two VEVENTs.
   e. Two policies → correct VEVENT count.
   f. SUMMARY escaping — commas, semicolons, backslashes in title are escaped.
   g. DTSTART value matches the exact expiry/renewal date.

All tests are offline — no live DB, no live JWT signing.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI

from app.api.v1 import calendar as calendar_module
from app.core.errors import register_error_handlers
from app.core.middleware import RequestIDMiddleware
from app.services.calendar_service import build_ics

# ---------------------------------------------------------------------------
# Minimal test app — calendar router only, same middleware + error handling as prod
# ---------------------------------------------------------------------------


def _make_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RequestIDMiddleware)
    register_error_handlers(test_app)
    test_app.include_router(calendar_module.router, prefix="/api/v1")
    return test_app


_test_app = _make_test_app()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_ORG_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _fake_policy(
    title: str = "Fleet Motor Insurance",
    category: str = "vehicle",
    policy_number: str | None = "POL-001",
    expiry_date: date | None = date(2026, 3, 31),
    renewal_date: date | None = None,
    sum_insured_inr: Decimal | None = Decimal("5000000.00"),
) -> MagicMock:
    """Return a MagicMock that looks like a Policy ORM object."""
    p = MagicMock()
    p.id = uuid.uuid4()
    p.tenant_id = uuid.UUID(_TENANT_ID)
    p.org_id = uuid.UUID(_ORG_ID)
    p.title = title
    p.category = category
    p.policy_number = policy_number
    p.sum_insured_inr = sum_insured_inr
    p.expiry_date = expiry_date
    p.renewal_date = renewal_date
    return p


# ---------------------------------------------------------------------------
# 1. Auth guard (endpoint-level)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calendar_endpoint_requires_auth():
    """No Bearer token → 401 with error code 'unauthorized'."""
    transport = httpx.ASGITransport(app=_test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/calendar.ics")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 2a. Empty policy list
# ---------------------------------------------------------------------------


def test_build_ics_empty_policies():
    """An empty policy list produces a valid VCALENDAR with no VEVENTs."""
    ics = build_ics([])
    assert "BEGIN:VCALENDAR" in ics
    assert "END:VCALENDAR" in ics
    assert "BEGIN:VEVENT" not in ics


# ---------------------------------------------------------------------------
# 2b. Policy without expiry_date → no VEVENT
# ---------------------------------------------------------------------------


def test_build_ics_no_expiry_skipped():
    """Policies without an expiry_date must produce no VEVENT."""
    policy = _fake_policy(expiry_date=None, renewal_date=None)
    ics = build_ics([policy])
    assert "BEGIN:VEVENT" not in ics


# ---------------------------------------------------------------------------
# 2c. Policy with expiry_date only → one VEVENT
# ---------------------------------------------------------------------------


def test_build_ics_expiry_only():
    """A policy with expiry_date but no renewal_date emits exactly one VEVENT."""
    policy = _fake_policy(expiry_date=date(2026, 3, 31), renewal_date=None)
    ics = build_ics([policy])

    assert ics.count("BEGIN:VEVENT") == 1
    assert ics.count("END:VEVENT") == 1

    # UID for expiry event
    assert f"{policy.id}-expiry@svault" in ics

    # All-day DTSTART using the correct date
    assert "DTSTART;VALUE=DATE:20260331" in ics

    # DTEND is the next day (exclusive)
    assert "DTEND;VALUE=DATE:20260401" in ics

    # Summary contains title
    assert "Fleet Motor Insurance" in ics

    # Envelope
    assert "BEGIN:VCALENDAR" in ics
    assert "END:VCALENDAR" in ics


# ---------------------------------------------------------------------------
# 2d. Policy with expiry_date + renewal_date → two VEVENTs
# ---------------------------------------------------------------------------


def test_build_ics_expiry_and_renewal():
    """A policy with both expiry_date and renewal_date emits two VEVENTs."""
    policy = _fake_policy(
        expiry_date=date(2026, 3, 31),
        renewal_date=date(2026, 4, 1),
    )
    ics = build_ics([policy])

    assert ics.count("BEGIN:VEVENT") == 2
    assert f"{policy.id}-expiry@svault" in ics
    assert f"{policy.id}-renewal@svault" in ics

    # Both dates present as DTSTART
    assert "DTSTART;VALUE=DATE:20260331" in ics
    assert "DTSTART;VALUE=DATE:20260401" in ics


# ---------------------------------------------------------------------------
# 2e. Two policies → correct VEVENT count
# ---------------------------------------------------------------------------


def test_build_ics_two_policies():
    """Two policies with expiry_date but no renewal_date → two VEVENTs."""
    p1 = _fake_policy(title="Policy A", expiry_date=date(2026, 6, 30))
    p2 = _fake_policy(title="Policy B", expiry_date=date(2026, 9, 30))
    ics = build_ics([p1, p2])
    assert ics.count("BEGIN:VEVENT") == 2


def test_build_ics_mixed_expiry():
    """Only policies with expiry_date contribute events; others are skipped."""
    p_with = _fake_policy(expiry_date=date(2026, 6, 30))
    p_without = _fake_policy(expiry_date=None)
    ics = build_ics([p_with, p_without])
    assert ics.count("BEGIN:VEVENT") == 1


# ---------------------------------------------------------------------------
# 2f. SUMMARY escaping
# ---------------------------------------------------------------------------


def test_build_ics_summary_escaping():
    """Commas, semicolons, and backslashes in the policy title must be escaped."""
    policy = _fake_policy(
        title=r"Fire\Flood; Plant, Factory",
        policy_number="POL-X",
        expiry_date=date(2026, 12, 31),
    )
    ics = build_ics([policy])

    # Comma escaped
    assert r"\," in ics
    # Semicolon escaped
    assert r"\;" in ics
    # Backslash escaped
    assert r"\\" in ics


# ---------------------------------------------------------------------------
# 2g. DTSTART matches exact expiry date
# ---------------------------------------------------------------------------


def test_build_ics_dtstart_matches_exact_date():
    """DTSTART;VALUE=DATE must exactly match the policy's expiry_date."""
    policy = _fake_policy(expiry_date=date(2027, 1, 15))
    ics = build_ics([policy])
    assert "DTSTART;VALUE=DATE:20270115" in ics


# ---------------------------------------------------------------------------
# 2h. CRLF line endings
# ---------------------------------------------------------------------------


def test_build_ics_crlf_line_endings():
    """The .ics output must use CRLF (\\r\\n) line endings throughout."""
    policy = _fake_policy(expiry_date=date(2026, 6, 30))
    ics = build_ics([policy])
    # Every line must end with \r\n
    assert "\r\n" in ics
    # No bare \n (i.e., every \n is preceded by \r).
    # Split on CRLF and verify no remaining newlines in any segment.
    for segment in ics.split("\r\n"):
        assert "\n" not in segment, f"Bare \\n found in segment: {segment!r}"


# ---------------------------------------------------------------------------
# 2i. PRODID and VERSION present
# ---------------------------------------------------------------------------


def test_build_ics_prodid_and_version():
    """The VCALENDAR wrapper must include VERSION:2.0 and PRODID:-//sVault//Renewals//EN."""
    ics = build_ics([])
    assert "VERSION:2.0" in ics
    assert "PRODID:-//sVault//Renewals//EN" in ics
