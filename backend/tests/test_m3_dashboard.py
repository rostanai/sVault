"""M3 dashboard tests — response schema + endpoint auth guard."""
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import httpx
import pytest

from app.main import app
from app.schemas.dashboard import (
    DashboardResponse,
    GroupDashboardResponse,
    OrgRollup,
    Totals,
)
from app.services import dashboard_service


def test_dashboard_response_validates_sample():
    sample = {
        "totals": {"policies": 3, "sum_insured_inr": "1000000.00",
                   "premium_inr": "25000.00", "lapsed": 1},
        "status_counts": {"active": 2, "lapsed": 1},
        "expiring": {"next_30": 1, "next_60": 2, "next_90": 2},
        "by_category": [{"category": "vehicle", "count": 2},
                        {"category": "plant", "count": 1}],
        "upcoming": [{"id": "00000000-0000-0000-0000-000000000001",
                      "title": "Fleet", "category": "vehicle",
                      "expiry_date": "2026-07-01", "status": "expiring", "days_left": 30}],
    }
    dr = DashboardResponse.model_validate(sample)
    assert dr.totals.policies == 3
    assert dr.expiring.next_30 == 1
    assert dr.upcoming[0].days_left == 30


@pytest.mark.asyncio
async def test_dashboard_requires_auth():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/dashboard")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


# ---- Group Dashboard ----

def test_group_dashboard_schema_validates_sample():
    """GroupDashboardResponse validates correctly shaped data."""
    org_id = str(uuid.uuid4())
    sample = {
        "totals": {
            "policies": 10,
            "sum_insured_inr": "5000000.00",
            "premium_inr": "120000.00",
            "lapsed": 2,
        },
        "by_org": [
            {
                "org_id": org_id,
                "org_name": "Parent Co.",
                "policies": 6,
                "sum_insured_inr": "3000000.00",
                "premium_inr": "80000.00",
                "expiring_30": 1,
            },
            {
                "org_id": str(uuid.uuid4()),
                "org_name": "Subsidiary Ltd.",
                "policies": 4,
                "sum_insured_inr": "2000000.00",
                "premium_inr": "40000.00",
                "expiring_30": 0,
            },
        ],
    }
    gdr = GroupDashboardResponse.model_validate(sample)
    assert gdr.totals.policies == 10
    assert len(gdr.by_org) == 2
    assert gdr.by_org[0].org_name == "Parent Co."
    assert gdr.by_org[0].sum_insured_inr == "3000000.00"
    assert gdr.by_org[1].expiring_30 == 0


def test_org_rollup_decimal_as_string():
    """OrgRollup stores monetary totals as strings (exact decimal representation)."""
    rollup = OrgRollup(
        org_id=uuid.uuid4(),
        org_name="Test Org",
        policies=5,
        sum_insured_inr="9999999.99",
        premium_inr="50000.00",
        expiring_30=3,
    )
    assert isinstance(rollup.sum_insured_inr, str)
    assert isinstance(rollup.premium_inr, str)
    assert rollup.sum_insured_inr == "9999999.99"


def test_group_dashboard_empty_by_org():
    """GroupDashboardResponse is valid with an empty by_org list."""
    gdr = GroupDashboardResponse(
        totals=Totals(
            policies=0,
            sum_insured_inr=Decimal("0"),
            premium_inr=Decimal("0"),
            lapsed=0,
        ),
        by_org=[],
    )
    assert gdr.by_org == []
    assert gdr.totals.policies == 0


@pytest.mark.asyncio
async def test_group_dashboard_requires_auth():
    """GET /dashboard/group returns 401 without a bearer token."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/dashboard/group")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_get_group_dashboard_service_shape():
    """Service returns GroupDashboardResponse with correct totals + by_org rows.

    Uses a fully-mocked DB session so no real database is needed.  The mock
    simulates two orgs: one with 6 policies (80 000 INR premium) and one with
    4 policies (40 000 INR premium).  Verifies:
    - totals are summed across all orgs,
    - by_org contains one OrgRollup per org,
    - monetary fields are strings,
    - ordering is premium desc.
    """
    from app.core.security import CurrentUser

    tenant_id = str(uuid.uuid4())
    org_a_id = uuid.uuid4()
    org_b_id = uuid.uuid4()

    user = CurrentUser(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        org_id=None,
        role="admin",
        is_super_admin=False,
    )

    # --- mock DB rows ---

    # Row returned by the group-wide totals query (count, sum_si, sum_prem)
    totals_row = (10, Decimal("5000000.00"), Decimal("120000.00"))

    # Rows returned by the status-count query
    status_rows = [("active", 8), ("lapsed", 2)]

    # Rows returned by per-org aggregation
    def _agg_row(org_id, policies, si, prem, exp30):
        r = MagicMock()
        r.org_id = org_id
        r.policies = policies
        r.sum_insured_inr = Decimal(si)
        r.premium_inr = Decimal(prem)
        r.expiring_30 = exp30
        return r

    agg_rows = [
        _agg_row(org_a_id, 6, "3000000.00", "80000.00", 1),
        _agg_row(org_b_id, 4, "2000000.00", "40000.00", 0),
    ]

    # Rows returned by org-name lookup
    org_name_rows = [(org_a_id, "Parent Co."), (org_b_id, "Subsidiary Ltd.")]

    # Build a mock execute result that returns the right data per call index
    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            # group-wide totals
            mock_result.one.return_value = totals_row
        elif call_count == 2:
            # status counts
            mock_result.all.return_value = status_rows
        elif call_count == 3:
            # per-org agg
            mock_result.all.return_value = agg_rows
        elif call_count == 4:
            # org name lookup
            mock_result.all.return_value = org_name_rows
        return mock_result

    mock_db = MagicMock()
    mock_db.execute = mock_execute

    result = await dashboard_service.get_group_dashboard(mock_db, user)

    assert isinstance(result, GroupDashboardResponse)

    # totals
    assert result.totals.policies == 10
    assert result.totals.lapsed == 2

    # by_org shape
    assert len(result.by_org) == 2

    # ordered premium desc: Parent Co. (80 000) before Subsidiary Ltd. (40 000)
    assert result.by_org[0].org_name == "Parent Co."
    assert result.by_org[1].org_name == "Subsidiary Ltd."

    # monetary values are strings
    assert isinstance(result.by_org[0].sum_insured_inr, str)
    assert isinstance(result.by_org[0].premium_inr, str)

    # expiring_30 counts
    assert result.by_org[0].expiring_30 == 1
    assert result.by_org[1].expiring_30 == 0
