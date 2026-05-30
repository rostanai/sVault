"""M3 dashboard tests — response schema + endpoint auth guard."""
import httpx
import pytest

from app.main import app
from app.schemas.dashboard import DashboardResponse


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
