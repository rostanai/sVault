"""M5 billing tests — entitlements logic, Razorpay sig verification,
secrets_store, endpoint auth guards, require_super_admin behaviour.

No live DB required — uses pure-function tests and the ASGI test client.
"""
from __future__ import annotations

import hashlib
import hmac
import uuid

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
    # Low finding fix: signature failures use validation_error, not unauthorized
    assert resp.json()["error"]["code"] == "validation_error"


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
    # Low finding fix: signature failures use validation_error, not unauthorized
    assert resp.json()["error"]["code"] == "validation_error"


# ---------------------------------------------------------------------------
# 7. ORM model smoke tests (no DB)
# ---------------------------------------------------------------------------

class TestBillingModels:
    def test_models_registered(self):
        from app.db.models import (
            BillingEvent,
            Invoice,
            Plan,
            PlatformAuditLog,
            PlatformSetting,
            Subscription,
        )
        assert Plan.__tablename__ == "plans"
        assert Subscription.__tablename__ == "subscriptions"
        assert Invoice.__tablename__ == "invoices"
        assert BillingEvent.__tablename__ == "billing_events"
        assert PlatformSetting.__tablename__ == "platform_settings"
        assert PlatformAuditLog.__tablename__ == "platform_audit_log"

    def test_mapper_configures(self):
        from sqlalchemy.orm import configure_mappers

        import app.db.models  # noqa: F401
        configure_mappers()  # raises if any FK / relationship is misconfigured


# ---------------------------------------------------------------------------
# 8. Security audit findings — C2, M1, H1/H2
# ---------------------------------------------------------------------------

class TestWebhookIdempotency:
    """C2 fix: webhook idempotency is atomic and id-less events are rejected."""

    @pytest.mark.asyncio
    async def test_idless_event_is_rejected(self):
        """C2: an event with no 'id' field must raise AppError(validation_error)."""
        from unittest.mock import AsyncMock, MagicMock

        from app.services.subscription_service import handle_webhook

        db = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()

        payload_without_id = {"event": "subscription.activated", "payload": {}}
        with pytest.raises(AppError) as exc:
            await handle_webhook(db, "subscription.activated", payload_without_id)
        assert exc.value.code.value == "validation_error"
        # Ensure db.flush was NOT called (rejected before any DB interaction)
        db.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_event_id_not_reprocessed(self):
        """C2: a duplicate event_id causes IntegrityError on flush → returns False
        WITHOUT applying any subscription status change."""
        from unittest.mock import AsyncMock, MagicMock

        from sqlalchemy.exc import IntegrityError

        from app.services.subscription_service import handle_webhook

        db = AsyncMock()
        db.add = MagicMock()
        # Simulate the unique constraint firing on flush (duplicate event_id).
        db.flush = AsyncMock(side_effect=IntegrityError("unique", {}, Exception()))
        db.rollback = AsyncMock()
        db.commit = AsyncMock()

        payload = {
            "id": "evt_duplicate_001",
            "event": "subscription.charged",
            "payload": {},
        }

        result = await handle_webhook(db, "subscription.charged", payload)

        assert result is False, "Duplicate event must return False"
        # db.commit must NOT be called after an IntegrityError
        db.commit.assert_not_called()
        db.rollback.assert_called_once()


class TestSubscribeNeverGrantsActiveStatus:
    """M1 fix: start_or_update_subscription must not persist status='active' without payment."""

    @pytest.mark.asyncio
    async def test_new_subscription_status_is_trialing_not_active(self):
        """M1: when Razorpay is skipped (no razorpay_plan_id), status must be 'trialing',
        never 'active'. Only a confirmed webhook may set 'active'."""
        import uuid as uuid_mod
        from unittest.mock import AsyncMock, MagicMock, patch

        from app.services.subscription_service import start_or_update_subscription

        plan_id = uuid_mod.UUID("00000000-0000-0000-0000-000000000010")
        tenant_id = uuid_mod.UUID("00000000-0000-0000-0000-000000000001")

        # Capture what Subscription is constructed with
        constructed_subs = []

        def capturing_init(self, **kwargs):
            constructed_subs.append(kwargs.get("status"))
            # Minimal init: just set the attrs the service reads
            self.tenant_id = kwargs.get("tenant_id")
            self.plan_id = kwargs.get("plan_id")
            self.status = kwargs.get("status", "trialing")
            self.razorpay_subscription_id = None

        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        # Mock the plan returned from the first DB execute
        mock_plan = MagicMock()
        mock_plan.id = plan_id
        mock_plan.is_active = True
        mock_plan.razorpay_plan_id = None  # no razorpay_plan_id → Razorpay call skipped

        # execute returns plan on first call, None (no existing subscription) on second
        plan_result = MagicMock()
        plan_result.scalar_one_or_none = MagicMock(return_value=mock_plan)
        no_sub_result = MagicMock()
        no_sub_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(side_effect=[plan_result, no_sub_result])

        import app.db.models.billing as billing_models

        # Patch Subscription.__init__ to capture the status kwarg
        with patch.object(billing_models.Subscription, "__init__", capturing_init):
            try:
                await start_or_update_subscription(db, tenant_id, plan_id)
            except Exception:
                pass  # refresh may fail on mock; that's fine

        # The subscription must have been constructed with status='trialing', not 'active'
        assert "trialing" in constructed_subs, (
            f"Expected status='trialing' for unpaid new sub, got {constructed_subs}"
        )
        assert "active" not in constructed_subs, (
            "Must NOT set status='active' without confirmed payment"
        )


class TestPlatformAuditLog:
    """H1 + H2 fix: Super Admin mutations write platform_audit_log rows."""

    @pytest.mark.asyncio
    async def test_create_plan_calls_audit(self):
        """H1: platform_service.create_plan must call _audit (write an audit row)."""
        from decimal import Decimal
        from unittest.mock import AsyncMock, MagicMock, patch

        import app.services.platform_service as ps
        from app.schemas.billing import PlanCreate

        payload = PlanCreate(
            tier="starter",
            name="Test Starter",
            price_inr=Decimal("999"),
        )
        actor_id = uuid.UUID("00000000-0000-0000-0000-000000000099")

        audit_calls = []

        async def mock_audit(db, actor, action, target, detail=None):
            audit_calls.append({"actor": actor, "action": action, "target": target})

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        # Mock Plan construction
        mock_plan = MagicMock()
        mock_plan.id = uuid.UUID("00000000-0000-0000-0000-000000000010")
        mock_plan.tier = "starter"
        mock_plan.name = "Test Starter"
        mock_plan.price_inr = Decimal("999")

        with patch.object(ps, "_audit", side_effect=mock_audit), \
             patch("app.services.platform_service.Plan", return_value=mock_plan):
            await ps.create_plan(db, payload, actor=actor_id)

        assert len(audit_calls) >= 1, "create_plan must write at least one audit row"
        assert audit_calls[0]["action"] == "create"
        assert audit_calls[0]["actor"] == actor_id

    @pytest.mark.asyncio
    async def test_set_setting_calls_audit(self):
        """H2: platform_service.set_setting must call _audit (secret write logged)."""
        from unittest.mock import AsyncMock, MagicMock, patch

        import app.services.platform_service as ps

        actor_id = uuid.UUID("00000000-0000-0000-0000-000000000099")
        audit_calls = []

        async def mock_audit(db, actor, action, target, detail=None):
            audit_calls.append({"actor": actor, "action": action, "target": target})

        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        # Simulate no existing setting (create path)
        no_row = MagicMock()
        no_row.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=no_row)

        from cryptography.fernet import Fernet
        test_key = Fernet.generate_key().decode()
        from app.core import config

        with patch.object(ps, "_audit", side_effect=mock_audit), \
             patch.object(config.settings, "secrets_encryption_key", test_key):
            await ps.set_setting(db, "razorpay_key_id", "rzp_test_xxx", is_secret=True,
                                 updated_by=actor_id)

        assert len(audit_calls) >= 1, "set_setting must write at least one audit row"
        assert audit_calls[0]["actor"] == actor_id
        assert audit_calls[0]["target"] == "razorpay_key_id"
        # The secret VALUE must NOT appear in the target
        assert "rzp_test_xxx" not in str(audit_calls[0].get("target", ""))

    @pytest.mark.asyncio
    async def test_suspend_tenant_calls_audit(self):
        """H1: platform_service.suspend_tenant must call _audit."""
        from unittest.mock import AsyncMock, MagicMock, patch

        import app.services.platform_service as ps
        from app.db.models.tenancy import Tenant as TenantModel

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        actor_id = uuid.UUID("00000000-0000-0000-0000-000000000099")
        audit_calls = []

        async def mock_audit(db, actor, action, target, detail=None):
            audit_calls.append({"actor": actor, "action": action, "target": target})

        mock_tenant = MagicMock(spec=TenantModel)
        mock_tenant.status = "active"

        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none = MagicMock(return_value=mock_tenant)

        db = AsyncMock()
        db.execute = AsyncMock(return_value=tenant_result)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        with patch.object(ps, "_audit", side_effect=mock_audit):
            await ps.suspend_tenant(db, tenant_id, actor=actor_id)

        assert len(audit_calls) >= 1, "suspend_tenant must write at least one audit row"
        assert audit_calls[0]["actor"] == actor_id
        assert audit_calls[0]["action"] == "update"
        assert str(tenant_id) in str(audit_calls[0]["target"])
