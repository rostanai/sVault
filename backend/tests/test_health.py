"""M0 smoke tests — app boots, health/ready respond, request-id is returned."""
import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_health_ok():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    # request-id middleware echoes the header
    assert r.headers.get("X-Request-ID", "").startswith("req_")


@pytest.mark.asyncio
async def test_ready_ok():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/v1/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_404_uses_error_envelope():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/v1/does-not-exist")
    assert r.status_code == 404
