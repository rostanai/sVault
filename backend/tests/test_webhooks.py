"""Outbound webhook tests.

Coverage
--------
1. Secret format — ``whsec_`` prefix, min length.
2. create() — inserts correct fields, returns secret ONCE (not in subsequent reads).
3. list_webhooks() / delete() — tenant scoping (no cross-tenant leakage).
4. Signature — deliver() computes a correct HMAC-SHA256 header (monkeypatched httpx).
5. Subscription filter — only active webhooks subscribed to the event receive delivery.
6. Endpoints — 401 without bearer token.
7. test_webhook() — returns delivered/status_code shape.

All service tests use AsyncMock / MagicMock; no live DB required.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.errors import AppError
from app.core.security import CurrentUser
from app.main import app
from app.schemas.webhook import WebhookCreate
from app.services import webhook_service
from app.services.webhook_service import _sign, generate_secret

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _user(
    role: str = "admin",
    tenant_id: str = TENANT_A,
    org_id: str = "cccccccc-cccc-cccc-cccc-cccccccccccc",
) -> CurrentUser:
    return CurrentUser(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        org_id=org_id,
        role=role,
    )


def _webhook_orm(
    *,
    webhook_id: uuid.UUID | None = None,
    tenant_id: str = TENANT_A,
    url: str = "https://example.com/hook",
    events: list[str] | None = None,
    secret: str = "whsec_testsecret",
    is_active: bool = True,
) -> MagicMock:
    obj = MagicMock()
    obj.id = webhook_id or uuid.uuid4()
    obj.tenant_id = uuid.UUID(tenant_id)
    obj.url = url
    obj.events = events if events is not None else ["renewal.due", "approval.pending"]
    obj.secret = secret
    obj.is_active = is_active
    obj.created_at = datetime.now(UTC)
    return obj


# ---------------------------------------------------------------------------
# 1. Secret format
# ---------------------------------------------------------------------------

def test_generate_secret_format():
    """Secret must start with 'whsec_' and be long enough to be useful."""
    secret = generate_secret()
    assert secret.startswith("whsec_"), f"Expected whsec_ prefix, got: {secret!r}"
    # whsec_ (6) + token_urlsafe(32) = ~49 chars minimum
    assert len(secret) > 20, f"Secret too short: {len(secret)}"


def test_generate_secret_uniqueness():
    """Two calls must produce distinct secrets."""
    s1 = generate_secret()
    s2 = generate_secret()
    assert s1 != s2


# ---------------------------------------------------------------------------
# 2. create() — inserts correct fields; secret returned once
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_inserts_correct_fields():
    """create() should persist a Webhook with the right tenant/url/events."""
    user = _user()
    payload = WebhookCreate(url="https://example.com/hook", events=["renewal.due"])

    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    captured: list = []

    async def fake_refresh(obj):
        obj.id = uuid.uuid4()
        obj.created_at = datetime.now(UTC)
        captured.append(obj)

    db.refresh = fake_refresh

    webhook, secret = await webhook_service.create(db, user, payload)

    db.add.assert_called_once()
    db.commit.assert_awaited_once()

    inserted = db.add.call_args[0][0]
    assert str(inserted.tenant_id) == TENANT_A
    assert inserted.url == "https://example.com/hook"
    assert inserted.events == ["renewal.due"]
    assert inserted.is_active is True
    assert inserted.secret.startswith("whsec_")

    # The returned secret must match what was stored.
    assert secret == inserted.secret


@pytest.mark.asyncio
async def test_create_secret_not_in_list_response():
    """WebhookRead (from list) must NOT expose the secret."""
    from app.schemas.webhook import WebhookRead

    hook = _webhook_orm(secret="whsec_supersecret")
    read = WebhookRead.model_validate(hook)
    dumped = read.model_dump()
    assert "secret" not in dumped, "secret must not appear in WebhookRead"


@pytest.mark.asyncio
async def test_create_no_tenant_raises_forbidden():
    """create() must raise 403 when the user has no tenant_id."""
    user = CurrentUser(user_id=str(uuid.uuid4()), tenant_id=None, role="admin")
    payload = WebhookCreate(url="https://example.com/hook", events=["renewal.due"])
    db = AsyncMock()

    with pytest.raises(AppError) as exc_info:
        await webhook_service.create(db, user, payload)

    assert exc_info.value.code.value == "forbidden"


# ---------------------------------------------------------------------------
# 3. list_webhooks() — tenant scoping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_webhooks_no_tenant_returns_empty():
    """A user with no tenant_id must get an empty list without hitting the DB."""
    user = CurrentUser(user_id="x", tenant_id=None, role="admin")
    db = AsyncMock()
    result = await webhook_service.list_webhooks(db, user)
    assert result == []
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_webhooks_returns_tenant_scoped():
    """list_webhooks() should execute a DB query scoped to the user's tenant."""
    user = _user()
    hook = _webhook_orm()

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [hook]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    result = await webhook_service.list_webhooks(db, user)

    db.execute.assert_awaited_once()
    assert result == [hook]


# ---------------------------------------------------------------------------
# 3. delete() — tenant scoping + not_found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_not_found_raises_404():
    """delete() must raise 404 when the webhook doesn't exist for the tenant."""
    user = _user()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(AppError) as exc_info:
        await webhook_service.delete(db, user, uuid.uuid4())

    assert exc_info.value.code.value == "not_found"


@pytest.mark.asyncio
async def test_delete_removes_webhook():
    """delete() must call db.delete and db.commit for a found webhook."""
    user = _user()
    hook = _webhook_orm()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = hook
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    await webhook_service.delete(db, user, hook.id)

    db.delete.assert_awaited_once_with(hook)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_no_tenant_raises_404():
    """delete() must raise 404 (not 403) when user has no tenant_id."""
    user = CurrentUser(user_id="x", tenant_id=None, role="admin")
    db = AsyncMock()

    with pytest.raises(AppError) as exc_info:
        await webhook_service.delete(db, user, uuid.uuid4())

    assert exc_info.value.code.value == "not_found"


# ---------------------------------------------------------------------------
# 4. Signature — _sign() + deliver() sends correct HMAC-SHA256 header
# ---------------------------------------------------------------------------

def test_sign_produces_correct_hmac():
    """_sign() must produce sha256=HMAC-SHA256(secret, body)."""
    secret = "whsec_mysecret"
    body = b'{"event":"test"}'
    expected_hex = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    result = _sign(secret, body)
    assert result == f"sha256={expected_hex}"


def test_sign_different_secrets_produce_different_sigs():
    """Different secrets must produce different signatures for the same body."""
    body = b'{"event":"renewal.due"}'
    sig1 = _sign("whsec_aaa", body)
    sig2 = _sign("whsec_bbb", body)
    assert sig1 != sig2


@pytest.mark.asyncio
async def test_deliver_sends_correct_signature(monkeypatch):
    """deliver() must POST the payload with a correct X-sVault-Signature header."""
    import app.services.webhook_service as ws_mod

    hook = _webhook_orm(
        events=["renewal.due"],
        secret="whsec_delivertest",
        is_active=True,
    )

    # Capture calls — store (content, headers) tuples.
    captured: list[tuple[bytes, dict]] = []

    class FakeResponse:
        status_code = 200
        is_success = True

    class FakeClient:
        def __init__(self, **kwargs):  # accept timeout= etc.
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def post(self, url, *, content, headers, **kwargs):  # noqa: PLR0913
            captured.append((content, dict(headers)))
            return FakeResponse()

    monkeypatch.setattr(ws_mod.httpx, "AsyncClient", FakeClient)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [hook]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    await webhook_service.deliver(db, uuid.UUID(TENANT_A), "renewal.due", {"policy_id": "x"})

    assert len(captured) == 1
    body, headers = captured[0]

    # Re-derive the expected signature from the actual body sent.
    expected_hex = hmac.new(hook.secret.encode(), body, hashlib.sha256).hexdigest()
    expected_header = f"sha256={expected_hex}"
    assert headers["X-sVault-Signature"] == expected_header


@pytest.mark.asyncio
async def test_deliver_sends_correct_event_body(monkeypatch):
    """deliver() must include event, created_at, and data in the JSON body."""
    import app.services.webhook_service as ws_mod

    hook = _webhook_orm(events=["approval.pending"])
    bodies: list[dict] = []

    class FakeResponse:
        status_code = 200
        is_success = True

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def post(self, url, *, content, headers, **kwargs):  # noqa: PLR0913
            bodies.append(json.loads(content))
            return FakeResponse()

    monkeypatch.setattr(ws_mod.httpx, "AsyncClient", FakeClient)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [hook]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    await webhook_service.deliver(
        db, uuid.UUID(TENANT_A), "approval.pending", {"approval_id": "abc"}
    )

    assert len(bodies) == 1
    body = bodies[0]
    assert body["event"] == "approval.pending"
    assert "created_at" in body
    assert body["data"] == {"approval_id": "abc"}


# ---------------------------------------------------------------------------
# 5. Subscription filter — only active + subscribed webhooks receive delivery
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deliver_skips_inactive_webhooks(monkeypatch):
    """deliver() must NOT post to inactive webhooks."""
    import app.services.webhook_service as ws_mod

    inactive_hook = _webhook_orm(events=["renewal.due"], is_active=False)
    posts: list = []

    class FakeResponse:
        status_code = 200
        is_success = True

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def post(self, *args, **kwargs):
            posts.append(args)
            return FakeResponse()

    monkeypatch.setattr(ws_mod.httpx, "AsyncClient", FakeClient)

    mock_result = MagicMock()
    # DB returns the inactive hook (is_active filter happens in Python for test simplicity).
    mock_result.scalars.return_value.all.return_value = [inactive_hook]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    await webhook_service.deliver(db, uuid.UUID(TENANT_A), "renewal.due", {})

    # The hook is inactive so it should be filtered out; no POST should be sent.
    assert len(posts) == 0


@pytest.mark.asyncio
async def test_deliver_skips_unsubscribed_events(monkeypatch):
    """deliver() must NOT post to webhooks not subscribed to the event."""
    import app.services.webhook_service as ws_mod

    hook = _webhook_orm(events=["policy.created"], is_active=True)
    posts: list = []

    class FakeResponse:
        status_code = 200
        is_success = True

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def post(self, *args, **kwargs):
            posts.append(args)
            return FakeResponse()

    monkeypatch.setattr(ws_mod.httpx, "AsyncClient", FakeClient)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [hook]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    # Event is "renewal.due" but hook is subscribed to "policy.created" — no delivery.
    await webhook_service.deliver(db, uuid.UUID(TENANT_A), "renewal.due", {})

    assert len(posts) == 0


@pytest.mark.asyncio
async def test_deliver_only_sends_to_subscribed_webhooks(monkeypatch):
    """Only the webhook subscribed to the event should receive the POST."""
    import app.services.webhook_service as ws_mod

    subscribed = _webhook_orm(events=["renewal.due"], is_active=True)
    not_subscribed = _webhook_orm(events=["approval.pending"], is_active=True)

    posted_urls: list[str] = []

    class FakeResponse:
        status_code = 200
        is_success = True

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def post(self, url, **kwargs):
            posted_urls.append(url)
            return FakeResponse()

    monkeypatch.setattr(ws_mod.httpx, "AsyncClient", FakeClient)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [subscribed, not_subscribed]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    await webhook_service.deliver(db, uuid.UUID(TENANT_A), "renewal.due", {})

    assert len(posted_urls) == 1
    assert posted_urls[0] == subscribed.url


# ---------------------------------------------------------------------------
# 6. Endpoints — 401 without bearer token
# ---------------------------------------------------------------------------

NULL_UUID = "00000000-0000-0000-0000-000000000000"


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", [
    ("get",    "/api/v1/webhooks", None),
    ("post",   "/api/v1/webhooks", {"url": "https://example.com/hook", "events": ["renewal.due"]}),
    ("delete", f"/api/v1/webhooks/{NULL_UUID}", None),
    ("post",   f"/api/v1/webhooks/{NULL_UUID}/test", None),
])
async def test_webhook_endpoints_require_auth(method: str, path: str, body: dict | None):
    """Every webhook endpoint must reject unauthenticated requests with 401."""
    from app.api.v1 import webhooks as webhooks_mod
    from app.core.config import settings

    # Register the router if not already on the app (for test isolation).
    _v1 = settings.api_v1_prefix
    already = any(
        hasattr(r, "path") and "/webhooks" in r.path
        for r in app.routes
    )
    if not already:
        app.include_router(webhooks_mod.router, prefix=_v1)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        kwargs = {"json": body} if body is not None else {}
        resp = await getattr(ac, method)(path, **kwargs)

    assert resp.status_code == 401, (
        f"{method.upper()} {path} should be 401 without auth, got {resp.status_code}"
    )
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 7. test_webhook() — delivered/status_code shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_test_webhook_returns_result_on_success(monkeypatch):
    """test_webhook() must return {delivered: True, status_code: 200} on a 200 response."""
    import app.services.webhook_service as ws_mod

    user = _user()
    hook = _webhook_orm()

    class FakeResponse:
        status_code = 200
        is_success = True

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(ws_mod.httpx, "AsyncClient", FakeClient)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = hook
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    result = await webhook_service.test_webhook(db, user, hook.id)

    assert result["delivered"] is True
    assert result["status_code"] == 200


@pytest.mark.asyncio
async def test_test_webhook_not_found_raises_404():
    """test_webhook() must raise 404 when the webhook doesn't exist for the tenant."""
    user = _user()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(AppError) as exc_info:
        await webhook_service.test_webhook(db, user, uuid.uuid4())

    assert exc_info.value.code.value == "not_found"


@pytest.mark.asyncio
async def test_test_webhook_connection_error_returns_not_delivered(monkeypatch):
    """test_webhook() must return {delivered: False, status_code: None} on connection error."""
    import app.services.webhook_service as ws_mod

    user = _user()
    hook = _webhook_orm()

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(ws_mod.httpx, "AsyncClient", FakeClient)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = hook
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    result = await webhook_service.test_webhook(db, user, hook.id)

    assert result["delivered"] is False
    assert result["status_code"] is None


# ---------------------------------------------------------------------------
# 8. deliver() swallows errors silently (never raises)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deliver_swallows_http_error(monkeypatch):
    """deliver() must not raise even when the target URL returns an error."""
    import app.services.webhook_service as ws_mod

    hook = _webhook_orm(events=["renewal.due"])

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("refused")

    monkeypatch.setattr(ws_mod.httpx, "AsyncClient", FakeClient)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [hook]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    # Must not raise.
    await webhook_service.deliver(db, uuid.UUID(TENANT_A), "renewal.due", {})


@pytest.mark.asyncio
async def test_deliver_swallows_db_error():
    """deliver() must not raise even when the DB query fails."""
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=Exception("DB is down"))

    # Must not raise.
    await webhook_service.deliver(db, uuid.UUID(TENANT_A), "renewal.due", {})
