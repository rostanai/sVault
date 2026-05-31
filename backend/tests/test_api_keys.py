"""API key management + public API tests.

Coverage
--------
1. generate_key() — format, prefix extraction, hash determinism.
2. Service-layer unit tests (no DB):
   a. create() — inserts correct fields, returns (obj, plaintext).
   b. list_keys() — returns empty list when no tenant_id.
   c. revoke() — 404 when key not found.
   d. authenticate() — valid key returns principal; revoked/garbage returns None.
3. Management endpoints (JWT-gated) — 401 without a bearer token.
4. Public endpoint — 401 without an API key header.

All service tests use AsyncMock and do NOT require a live DB.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.api.v1 import api_keys as api_keys_router_mod
from app.api.v1 import public as public_router_mod
from app.core.config import settings
from app.core.errors import AppError
from app.core.security import CurrentUser
from app.main import app
from app.schemas.api_key import ApiKeyCreate
from app.services import api_key_service
from app.services.api_key_service import generate_key

# ---------------------------------------------------------------------------
# One-time router registration
# ---------------------------------------------------------------------------
# The production router.py (read-only) will include these routers when wired up.
# For test isolation we register them here if not yet present on the app.
_V1_PREFIX = settings.api_v1_prefix  # e.g. "/api/v1"

def _routes_registered() -> bool:
    """Return True if api-keys routes are already on the app."""
    return any(
        hasattr(r, "path") and "/api-keys" in r.path
        for r in app.routes
    )

if not _routes_registered():
    app.include_router(api_keys_router_mod.router, prefix=_V1_PREFIX)
    app.include_router(public_router_mod.router, prefix=_V1_PREFIX)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(
    role: str = "admin",
    tenant_id: str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    org_id: str = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
) -> CurrentUser:
    return CurrentUser(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        org_id=org_id,
        role=role,
    )


def _api_key_orm(
    *,
    key_id: uuid.UUID | None = None,
    revoked_at: datetime | None = None,
    key_hash: str = "",
    scopes: list[str] | None = None,
) -> MagicMock:
    obj = MagicMock()
    obj.id = key_id or uuid.uuid4()
    obj.tenant_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    obj.name = "Test key"
    obj.key_prefix = "svk_a1b2c3d4"
    obj.key_hash = key_hash
    obj.scopes = scopes or []
    obj.rate_limit_per_min = 60
    obj.last_used_at = None
    obj.revoked_at = revoked_at
    obj.created_by = uuid.uuid4()
    obj.created_at = datetime.now(UTC)
    return obj


# ---------------------------------------------------------------------------
# 1. generate_key() — format + determinism
# ---------------------------------------------------------------------------

def test_generate_key_format():
    """Key must start with svk_, have 3 underscore-separated parts."""
    plaintext, prefix, key_hash = generate_key()

    parts = plaintext.split("_", 2)
    assert len(parts) == 3, f"Expected 3 parts, got: {plaintext!r}"
    assert parts[0] == "svk"
    assert len(parts[1]) == 8, "8-char hex prefix expected"
    assert len(parts[2]) >= 32, "Secret part should be at least 32 chars"
    assert prefix == f"svk_{parts[1]}"


def test_generate_key_prefix_matches():
    """Prefix returned must match the svk_<8char> part of the plaintext."""
    plaintext, prefix, _ = generate_key()
    assert plaintext.startswith(prefix)


def test_generate_key_hash_is_sha256_hex():
    """key_hash must be SHA-256 hex of the plaintext."""
    plaintext, _, key_hash = generate_key()
    expected = hashlib.sha256(plaintext.encode()).hexdigest()
    assert key_hash == expected


def test_generate_key_hash_is_deterministic():
    """The same plaintext always produces the same hash."""
    plaintext, _, _ = generate_key()
    h1 = hashlib.sha256(plaintext.encode()).hexdigest()
    h2 = hashlib.sha256(plaintext.encode()).hexdigest()
    assert h1 == h2


def test_generate_key_uniqueness():
    """Two generate_key() calls must produce different plaintexts."""
    p1, _, _ = generate_key()
    p2, _, _ = generate_key()
    assert p1 != p2


# ---------------------------------------------------------------------------
# 2a. create() — inserts correct fields, returns plaintext
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_inserts_correct_fields():
    """create() should insert an ApiKey row and return a non-empty plaintext."""
    user = _user()
    payload = ApiKeyCreate(name="CI key", scopes=["policy:read"], rate_limit_per_min=30)

    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    captured: list = []

    async def fake_refresh(obj):
        captured.append(obj)

    db.refresh = fake_refresh

    api_key_obj, plaintext = await api_key_service.create(db, user, payload)

    db.add.assert_called_once()
    db.commit.assert_awaited_once()

    inserted = db.add.call_args[0][0]
    assert str(inserted.tenant_id) == user.tenant_id
    assert str(inserted.created_by) == user.user_id
    assert inserted.name == "CI key"
    assert inserted.scopes == ["policy:read"]
    assert inserted.rate_limit_per_min == 30
    assert inserted.key_prefix.startswith("svk_")
    assert len(inserted.key_hash) == 64  # SHA-256 hex

    assert plaintext.startswith("svk_")
    assert len(plaintext) > 20


@pytest.mark.asyncio
async def test_create_plaintext_matches_hash():
    """The plaintext returned by create() must hash to the stored key_hash."""
    user = _user()
    payload = ApiKeyCreate(name="Hash check")

    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    _, plaintext = await api_key_service.create(db, user, payload)
    inserted = db.add.call_args[0][0]

    expected_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    assert inserted.key_hash == expected_hash


@pytest.mark.asyncio
async def test_create_no_tenant_raises_forbidden():
    """create() must raise 403 when the user has no tenant_id."""
    user = CurrentUser(user_id=str(uuid.uuid4()), tenant_id=None, role="admin")
    payload = ApiKeyCreate(name="orphan key")
    db = AsyncMock()

    with pytest.raises(AppError) as exc_info:
        await api_key_service.create(db, user, payload)

    assert exc_info.value.code.value == "forbidden"


# ---------------------------------------------------------------------------
# 2b. list_keys() — no tenant returns empty list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_keys_no_tenant_returns_empty():
    """A user with no tenant_id must get an empty list, not an error."""
    user = CurrentUser(user_id="x", tenant_id=None, role="admin")
    db = AsyncMock()
    result = await api_key_service.list_keys(db, user)
    assert result == []
    db.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# 2c. revoke() — 404 when key not found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revoke_not_found_raises_404():
    """revoke() must raise 404 when the key doesn't exist for the tenant."""
    user = _user()

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(AppError) as exc_info:
        await api_key_service.revoke(db, user, uuid.uuid4())

    assert exc_info.value.code.value == "not_found"


@pytest.mark.asyncio
async def test_revoke_sets_revoked_at():
    """revoke() must set revoked_at on the found key and commit."""
    user = _user()
    key_obj = _api_key_orm()

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = key_obj
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    await api_key_service.revoke(db, user, key_obj.id)

    assert key_obj.revoked_at is not None
    db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 2d. authenticate() — valid key succeeds; revoked / garbage → None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_authenticate_valid_key_returns_principal():
    """authenticate() with a valid key must return an ApiKeyPrincipal."""
    plaintext, _, key_hash = generate_key()
    key_obj = _api_key_orm(key_hash=key_hash, scopes=["policy:read"])

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = key_obj
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    principal = await api_key_service.authenticate(db, plaintext)

    assert principal is not None
    assert principal.tenant_id == key_obj.tenant_id
    assert principal.key_id == key_obj.id
    assert principal.scopes == ["policy:read"]


@pytest.mark.asyncio
async def test_authenticate_revoked_key_returns_none():
    """authenticate() must return None when the key is revoked (DB lookup returns None)."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # simulates revoked/missing
    db.execute = AsyncMock(return_value=mock_result)

    _, _, _ = generate_key()
    result = await api_key_service.authenticate(db, "svk_deadbeef_invalidsecret")

    assert result is None


@pytest.mark.asyncio
async def test_authenticate_garbage_key_returns_none():
    """authenticate() must return None for a completely invalid key string."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    result = await api_key_service.authenticate(db, "not-a-real-key-at-all")
    assert result is None


# ---------------------------------------------------------------------------
# 3. Management endpoints — 401 without a JWT
# ---------------------------------------------------------------------------

NULL_UUID = "00000000-0000-0000-0000-000000000000"


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", [
    ("get",    "/api/v1/api-keys",             None),
    ("post",   "/api/v1/api-keys",             {"name": "k"}),
    ("delete", f"/api/v1/api-keys/{NULL_UUID}", None),
])
async def test_management_endpoints_require_jwt(method: str, path: str, body: dict | None):
    """Every management endpoint must return 401 without a bearer token."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        kwargs = {"json": body} if body is not None else {}
        resp = await getattr(ac, method)(path, **kwargs)

    assert resp.status_code == 401, (
        f"{method.upper()} {path} should be 401 without auth, got {resp.status_code}"
    )
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 4. Public endpoint — 401 without an API key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_public_policies_requires_api_key():
    """GET /public/v1/policies must return 401 when no API key is provided."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/public/v1/policies")

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_public_policies_rejects_invalid_key():
    """GET /public/v1/policies with an invalid key must return 401.

    We override get_db so the request reaches the auth service (which hashes
    the garbage key, finds nothing in the mock DB, and raises 401) without
    needing a real DATABASE_URL.
    """
    from app.db.session import get_db

    # Build a mock DB session whose execute() returns "key not found" (None).
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()

    async def _override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                "/api/v1/public/v1/policies",
                headers={"X-API-Key": "svk_garbage_thisisnotavalidkey12345"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 5. Permission matrix — apikey:manage
# ---------------------------------------------------------------------------

from app.core.authz import has_permission  # noqa: E402


@pytest.mark.parametrize("role,expected", [
    ("admin",   True),
    ("manager", False),
    ("owner",   False),
    ("viewer",  False),
])
def test_apikey_manage_permission_matrix(role: str, expected: bool):
    """Only Admin may manage API keys per PERMISSIONS.md."""
    user = _user(role=role)
    assert has_permission(user, "apikey:manage") is expected
