"""User/team-management tests — endpoint auth guards + last-admin guard logic."""
import httpx
import pytest

from app.main import app
from app.services.user_service import would_remove_last_admin


def test_last_admin_guard_blocks_demoting_sole_admin():
    # Sole active admin demoted to manager -> blocked.
    assert would_remove_last_admin(
        target_is_admin=True, admin_count=1, new_role="manager", new_is_active=True
    )
    # Sole active admin deactivated (still admin role) -> blocked.
    assert would_remove_last_admin(
        target_is_admin=True, admin_count=1, new_role="admin", new_is_active=False
    )


def test_last_admin_guard_allows_when_other_admins_exist():
    # Another admin remains -> demotion allowed.
    assert not would_remove_last_admin(
        target_is_admin=True, admin_count=2, new_role="manager", new_is_active=True
    )


def test_last_admin_guard_allows_non_admin_and_kept_admin():
    # Target isn't an admin -> never blocked.
    assert not would_remove_last_admin(
        target_is_admin=False, admin_count=1, new_role="viewer", new_is_active=True
    )
    # Sole admin kept as active admin -> allowed.
    assert not would_remove_last_admin(
        target_is_admin=True, admin_count=1, new_role="admin", new_is_active=True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/users"),
    ("patch", "/api/v1/users/00000000-0000-0000-0000-000000000000"),
    ("get", "/api/v1/invitations"),
])
async def test_user_endpoints_require_auth(method, path):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        kwargs = {"json": {"role": "viewer"}} if method == "patch" else {}
        resp = await getattr(ac, method)(path, **kwargs)
    # No bearer token -> 401 with the error envelope (before any DB access).
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"
