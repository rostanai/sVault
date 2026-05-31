"""Tests for the weekly renewal email digest.

Coverage:
- POST /digests/dispatch without X-Cron-Secret -> 404 (endpoint hidden).
- POST /digests/send-me without a bearer token -> 401.
- build_digest_text: with policies -> includes title + "expiring"; empty -> "no upcoming".
- send_for_tenant (mocked DB + monkeypatched email adapter) -> sent=True + correct count.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.api.v1 import digests as digests_router_module
from app.core.config import settings
from app.main import app
from app.services.digest_service import build_digest_text, send_for_tenant

# Register the digests router onto the live app under test.  This is the
# equivalent of the two lines the tech-lead must add to router.py:
#
#   from app.api.v1 import digests
#   api_router.include_router(digests.router)
#
# We do it here (idempotently) so the endpoint tests work without modifying
# router.py (which is out of scope for this task).
_DIGEST_PREFIX = f"{settings.api_v1_prefix}/digests"
_already_registered = any(
    getattr(r, "path", "").startswith(_DIGEST_PREFIX)
    for r in app.routes
)
if not _already_registered:
    app.include_router(digests_router_module.router, prefix=settings.api_v1_prefix)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_policy(
    title: str = "Factory Fire Cover",
    category: str = "factory_property",
    expiry_date: date | None = None,
    premium_inr: Decimal | None = Decimal("150000.00"),
) -> MagicMock:
    p = MagicMock()
    p.title = title
    p.category = category
    p.expiry_date = expiry_date or (date.today() + timedelta(days=15))
    p.premium_inr = premium_inr
    return p


def _make_db_with_policies(policies: list) -> MagicMock:
    """Return a fake AsyncSession whose execute().scalars().all() yields *policies*."""
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=policies)

    execute_result = MagicMock()
    execute_result.scalars = MagicMock(return_value=scalars_mock)

    db = MagicMock()
    db.execute = AsyncMock(return_value=execute_result)
    return db


# ---------------------------------------------------------------------------
# Endpoint guard tests (no DB needed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_without_cron_secret_returns_404():
    """POST /digests/dispatch without X-Cron-Secret must return 404 (endpoint hidden)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/digests/dispatch")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_send_me_without_token_returns_401():
    """POST /digests/send-me without a bearer token must return 401."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/digests/send-me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# build_digest_text — pure function, no DB
# ---------------------------------------------------------------------------

def test_build_digest_text_includes_policy_titles():
    """Digest body must mention policy titles and the word 'expiring'."""
    p1 = _make_policy(title="Vehicle Fleet Cover", expiry_date=date.today() + timedelta(days=10))
    p2 = _make_policy(
        title="Plant & Machinery Policy",
        expiry_date=date.today() + timedelta(days=25),
    )

    text = build_digest_text([p1, p2])

    assert "Vehicle Fleet Cover" in text
    assert "Plant & Machinery Policy" in text
    # Must contain a word signalling expiry.
    assert "expir" in text.lower()


def test_build_digest_text_single_policy_mentions_days_left():
    """Digest text must include the number of days left for a single policy."""
    expiry = date.today() + timedelta(days=7)
    p = _make_policy(title="Key Person Cover", expiry_date=expiry)

    text = build_digest_text([p])

    assert "Key Person Cover" in text
    assert "7" in text  # days left


def test_build_digest_text_empty_returns_no_upcoming_line():
    """Empty policy list must yield a 'no upcoming renewals' notice."""
    text = build_digest_text([])

    lower = text.lower()
    assert "no upcoming" in lower or "all clear" in lower


def test_build_digest_text_branded_header():
    """Digest must carry the sVault brand in its header."""
    text = build_digest_text([])
    assert "sVault" in text


def test_build_digest_text_sorted_soonest_first():
    """Policies must appear in ascending expiry order (soonest first)."""
    far = _make_policy(title="Far Policy", expiry_date=date.today() + timedelta(days=29))
    near = _make_policy(title="Near Policy", expiry_date=date.today() + timedelta(days=3))

    text = build_digest_text([far, near])  # deliberately reversed input order

    near_pos = text.index("Near Policy")
    far_pos = text.index("Far Policy")
    assert near_pos < far_pos, "Soonest-expiring policy must appear first in digest"


# ---------------------------------------------------------------------------
# send_for_tenant — mocked DB + monkeypatched email adapter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_for_tenant_returns_sent_true_simulated():
    """send_for_tenant returns sent=True and correct policy count (simulated mode)."""
    tenant_id = uuid.uuid4()
    p1 = _make_policy(title="Group Health Plan")
    p2 = _make_policy(title="Stock RM Cover")

    db = _make_db_with_policies([p1, p2])

    from app.services.notifications.base import SendResult

    with patch(
        "app.services.digest_service.email_adapter.send",
        new=AsyncMock(return_value=SendResult(status="simulated", provider_msg_id="sim-x")),
    ):
        result = await send_for_tenant(db, tenant_id, "admin@example.com")

    assert result["sent"] is True
    assert result["recipient"] == "admin@example.com"
    assert result["policies"] == 2


@pytest.mark.asyncio
async def test_send_for_tenant_zero_policies():
    """send_for_tenant with no expiring policies still returns sent=True (digest sent)."""
    tenant_id = uuid.uuid4()

    db = _make_db_with_policies([])

    from app.services.notifications.base import SendResult

    with patch(
        "app.services.digest_service.email_adapter.send",
        new=AsyncMock(return_value=SendResult(status="simulated", provider_msg_id="sim-y")),
    ):
        result = await send_for_tenant(db, tenant_id, "admin@example.com")

    assert result["sent"] is True
    assert result["policies"] == 0


@pytest.mark.asyncio
async def test_send_for_tenant_accepts_string_tenant_id():
    """send_for_tenant coerces a string tenant_id without raising."""
    tenant_id = str(uuid.uuid4())
    db = _make_db_with_policies([])

    from app.services.notifications.base import SendResult

    with patch(
        "app.services.digest_service.email_adapter.send",
        new=AsyncMock(return_value=SendResult(status="simulated", provider_msg_id="sim-z")),
    ):
        result = await send_for_tenant(db, tenant_id, "x@example.com")

    assert result["sent"] is True
