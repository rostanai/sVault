"""Regression: 500 responses must carry CORS headers.

The catch-all Exception handler runs in Starlette's ServerErrorMiddleware, which sits
*outside* CORSMiddleware. Without re-adding CORS headers, a 500 reaches the browser with
no Access-Control-Allow-Origin and is masked as a misleading "blocked by CORS policy"
error — hiding the real failure. These tests lock in that 500s echo an allowed Origin.
"""
import httpx
import pytest
from fastapi import FastAPI

from app.core.errors import register_error_handlers


def _app_that_blows_up() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def _boom() -> dict:
        raise RuntimeError("kaboom")  # triggers the catch-all 500 handler

    return app


@pytest.mark.asyncio
async def test_500_echoes_allowed_origin(monkeypatch):
    """A 500 must include Access-Control-Allow-Origin for an allowed origin."""
    from app.core import config

    monkeypatch.setattr(config.settings, "cors_origins", "https://svault.rstglobal.in")

    app = _app_that_blows_up()
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/boom", headers={"Origin": "https://svault.rstglobal.in"})

    assert resp.status_code == 500
    assert resp.headers.get("access-control-allow-origin") == "https://svault.rstglobal.in"
    assert resp.headers.get("access-control-allow-credentials") == "true"
    # The real error envelope is now visible to the browser (no longer masked as CORS).
    assert resp.json()["error"]["code"] == "internal_error"


@pytest.mark.asyncio
async def test_500_omits_header_for_disallowed_origin(monkeypatch):
    """A 500 must NOT echo an origin that isn't in the allow-list."""
    from app.core import config

    monkeypatch.setattr(config.settings, "cors_origins", "https://svault.rstglobal.in")

    app = _app_that_blows_up()
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/boom", headers={"Origin": "https://evil.example.com"})

    assert resp.status_code == 500
    assert "access-control-allow-origin" not in resp.headers
