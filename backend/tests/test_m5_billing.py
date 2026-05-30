"""M5 billing tests — entitlements logic, Razorpay sig verification,
secrets_store, endpoint auth guards, require_super_admin behaviour.

No live DB required — uses pure-function tests and the ASGI test client.
"""
from __future__ import annotations

import hashlib
import hmac

import httpx
import pytest

from app.core.errors import AppError
from app.core.security import CurrentUser
from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(
    role: str = "admin",
    super_admin: bool = False,
    tenant_id: str = "00000000-0000-0000-0000-000000000001",
) -> CurrentUser:
    return CurrentUser(
        user_id="00000000-0000-0000-0000-000000000099",
        tenant_id=tenant_id,
        org_id="00000000-0000-0000-0000-000000000002",
        role=role,
        is_super_admin=super_admin,
    )


# ---------------------------------------------------------------------------
# 1. Pure entitlement helpers — feature_allowed + within_limit
# ---------------------------------------------------------------------------

class TestEntitlementHelpers:
    def setup_method(self):
        from app.services.entitlements import feature_allowed, within_limit
        self.feature_allowed = feature_allowed
        self.within_limit = within_limit

    def test_feature_allowed_true(self):
        ents = {"features": {"rag": True, "sms": False}}
        assert self.feature_allowed(ents, "rag") is True

    def test_feature_allowed_false(self):
        ents = {"features": {"rag": True, "sms": False}}
        assert self.feature_allowed(ents, "sms") is False

    def test_feature_allowed_missing_key_returns_false(self):
        assert self.feature_allowed({"features": {}}, "nonexistent") is False

    def test_feature_allowed_empty_dict_returns_false(self):
        assert self.feature_allowed({}, "rag") is False

    def test_within_limit_under_cap(self):
        ents = {"limits": {"policies": 10}}
        assert self.within_limit(ents, "policies", 5) is True

    def test_within_limit_at_cap_is_blocked(self):
        # count >= limit is blocked (within_limit is strictly count < limit)
        ents = {"limits": {"policies": 10}}
        assert self.within_limit(ents, "policies", 10) is False

    def test_within_limit_unlimited_minus_one(self):
        ents = {"limits": {"policies": -1}}
        assert self.within_limit(ents, "policies", 99999) is True

    def test_within_limit_missing_key_is_unlimited(self):
        assert self.within_limit({"limits": {}}, "documents", 500) is True

    def test_within_limit_no_limits_section(self):
        assert self.within_limit({}, "users", 0) is True

    def test_free_vs_pro_entitlements(self):
        from app.services.entitlements import _FREE_ENTITLEMENTS, _PRO_ENTITLEMENTS

        # Free: no RAG, no SMS
        assert self.feature_allowed(_FREE_ENTITLEMENTS, "rag") is False
        assert self.feature_allowed(_FREE_ENTITLEMENTS, "sms_alerts") is False
        assert self.feature_allowed(_FREE_ENTITLEMENTS, "email_alerts") is True

        # Pro: has RAG, SMS, API
        assert self.feature_allowed(_PRO_ENTITLEMENTS, "rag") is True
        assert self.feature_allowed(_PRO_ENTITLEMENTS, "sms_alerts") is True
        assert self.feature_allowed(_PRO_ENTITLEMENTS, "api") is True

        # Free: 10-policy limit; Pro: unlimited (-1)
        assert self.within_limit(_FREE_ENTITLEMENTS, "policies", 9) is True
        assert self.within_limit(_FREE_ENTITLEMENTS, "policies", 10) is False
        assert self.within_limit(_PRO_ENTITLEMENTS, "policies", 999999) is True


# ---------------------------------------------------------------------------
# 2. Razorpay webhook signature verification — pure function
# ---------------------------------------------------------------------------

class TestWebhookSignature:
    def _sig(self, body: bytes, secret: str) -> str:
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def test_valid_signature(self, monkeypatch):
        from app.core import config
        monkeypatch.setattr(config.settings, "razorpay_webhook_secret", "test-secret")
        from app.core import razorpay as rzp
        monkeypatch.setattr(rzp.settings, "razorpay_webhook_secret", "test-secret")

        body = b'{"event":"subscription.activated"}'
        sig = self._sig(body, "test-secret")
        assert rzp.verify_webhook_signature(body, sig) is True

    def test_tampered_body_rejected(self, monkeypatch):
        from app.core import config
        monkeypatch.setattr(config.settings, "razorpay_webhook_secret", "test-secret")
        from app.core import razorpay as rzp
        monkeypatch.setattr(rzp.settings, "razorpay_webhook_secret", "test-secret")

        body = b'{"event":"subscription.activated"}'
        sig = self._sig(body, "test-secret")
        tampered = body + b"evil"
        assert rzp.verify_webhook_signature(tampered, sig) is False

    def test_wrong_secret_rejected(self, monkeypatch):
        from app.core import config
        monkeypatch.setattr(config.settings, "razorpay_webhook_secret", "correct-secret")
        from app.core import razorpay as rzp
        monkeypatch.setattr(rzp.settings, "razorpay_webhook_secret", "correct-secret")

        body = b'{"event":"payment.failed"}'
        sig = self._sig(body, "wrong-secret")
        assert rzp.verify_webhook_signature(body, sig) is False

    def test_unconfigured_secret_returns_false(self, monkeypatch):
        from app.core import config
        monkeypatch.setattr(config.settings, "razorpay_webhook_secret", "")
        from app.core import razorpay as rzp
        monkeypatch.setattr(rzp.settings, "razorpay_webhook_secret", "")

        assert rzp.verify_webhook_signature(b"anything", "somesig") is False


# ---------------------------------------------------------------------------
# 3. Secrets store — encrypt / decrypt round-trip; ciphertext != plaintext
# ---------------------------------------------------------------------------

class TestSecretsStore:
    def _store(self, monkeypatch):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        from app.core import config, secrets_store
        monkeypatch.setattr(config.settings, "secrets_encryption_key", key)
        monkeypatch.setattr(secrets_store.settings, "secrets_encryption_key", key)
        return secrets_store

    def test_round_trip(self, monkeypatch):
        store = self._store(monkeypatch)
        token = store.encrypt("my-api-key-12345")
        assert store.decrypt(token) == "my-api-key-12345"

    def test_ciphertext_not_plaintext(self, monkeypatch):
        store = self._store(monkeypatch)
        plaintext = "supersecretrazorpaykey"
        token = store.encrypt(plaintext)
        assert token != plaintext
        assert plaintext not in token

    def test_mask_always_hides_value(self, monkeypatch):
        store = self._store(monkeypatch)
        token = store.encrypt("real-api-key")
        assert store.mask(token) == "**ENCRYPTED**"
        assert "real-api-key" not in store.mask(token)

    def test_mask_empty_returns_empty(self, monkeypatch):
        store = self._store(monkeypatch)
        assert store.mask(None) == ""
        assert store.mask("") == ""

    def test_missing_key_raises_internal_error(self, monkeypatch):
        from app.core import config, secrets_store
        monkeypatch.setattr(config.settings, "secrets_encryption_key", "")
        monkeypatch.setattr(secrets_store.settings, "secrets_encryption_key", "")
        with pytest.raises(AppError) as exc:
            secrets_store.encrypt("value")
        assert exc.value.code.value == "internal_error"


# ---------------------------------------------------------------------------
# 4. require_super_admin — 404 (not 403) for non-super-admin users
# ---------------------------------------------------------------------------

class TestRequireSuperAdmin:
    def test_non_super_admin_gets_404(self):
        from app.core.authz import require_super_admin
        for role in ("admin", "manager", "owner", "viewer"):
            with pytest.raises(AppError) as exc:
                require_super_admin(_user(role=role))
            assert exc.value.code.value == "not_found", (
                f"role={role} should produce not_found (404), not forbidden"
            )

    def test_super_admin_passes(self):
        from app.core.authz import require_super_admin
        result = require_super_admin(_user(super_admin=True))
        assert result.is_super_admin is True


# ---------------------------------------------------------------------------
# 5. Endpoint auth guards — 401 without a token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/plans"),
    ("get", "/api/v1/billing/subscription"),
    ("post", "/api/v1/billing/subscribe"),
])
async def test_billing_endpoints_require_auth(method, path):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        kwargs = {"json": {}} if method == "post" else {}
        resp = await getattr(ac, method)(path, **kwargs)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


# Platform endpoints guarded by require_super_admin: without a token → 401.
@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/platform/plans"),
    ("post", "/api/v1/platform/plans"),
    ("get", "/api/v1/platform/tenants"),
])
async def test_platform_endpoints_require_auth(method, path):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        kwargs = {"json": {}} if method == "post" else {}
        resp = await getattr(ac, method)(path, **kwargs)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 6. Webhook endpoint — 400 without a valid signature (before DB access)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_missing_signature_returns_400():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/billing/webhook",
            content=b'{"event":"subscription.activated"}',
            headers={"Content-Type": "application/json"},
            # No X-Razorpay-Signature header
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_400(monkeypatch):
    from app.core import config
    monkeypatch.setattr(config.settings, "razorpay_webhook_secret", "real-secret")
    # Import the razorpay module and patch its settings reference too
    from app.core import razorpay as rzp
    monkeypatch.setattr(rzp.settings, "razorpay_webhook_secret", "real-secret")

    body = b'{"event":"subscription.activated"}'
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/billing/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": "badhex000000000000000000000000000000000000",
            },
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 7. ORM model smoke tests (no DB)
# ---------------------------------------------------------------------------

class TestBillingModels:
    def test_models_registered(self):
        from app.db.models import BillingEvent, Invoice, Plan, PlatformSetting, Subscription
        assert Plan.__tablename__ == "plans"
        assert Subscription.__tablename__ == "subscriptions"
        assert Invoice.__tablename__ == "invoices"
        assert BillingEvent.__tablename__ == "billing_events"
        assert PlatformSetting.__tablename__ == "platform_settings"

    def test_mapper_configures(self):
        from sqlalchemy.orm import configure_mappers

        import app.db.models  # noqa: F401
        configure_mappers()  # raises if any FK / relationship is misconfigured
