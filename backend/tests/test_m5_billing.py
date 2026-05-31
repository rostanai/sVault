"""M5 billing tests — entitlements logic, Razorpay sig verification,
secrets_store, endpoint auth guards, require_super_admin behaviour.

No live DB required — uses pure-function tests and the ASGI test client.
"""
from __future__ import annotations

import hashlib
import hmac
import uuid
from unittest.mock import AsyncMock, MagicMock

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


class TestSubscribeNeverGrantsActiveStatusInRealMode:
    """M1 fix (updated): start_or_update_subscription must not persist status='active'
    when real Razorpay credentials AND plan.razorpay_plan_id are both set.
    Only a confirmed webhook may set 'active' in that path."""

    @pytest.mark.asyncio
    async def test_real_mode_status_is_not_forced_active(self):
        """Branch 1: with razorpay_key_id set AND plan.razorpay_plan_id set,
        status must NOT be forced to 'active' locally — the webhook does that.
        Returns payment_required=True and a short_url.
        Uses db.add capture (avoids patching SQLAlchemy __init__)."""
        import uuid as uuid_mod
        from unittest.mock import AsyncMock, MagicMock, patch

        from app.core import config
        from app.services.subscription_service import start_or_update_subscription

        plan_id = uuid_mod.UUID("00000000-0000-0000-0000-000000000010")
        tenant_id = uuid_mod.UUID("00000000-0000-0000-0000-000000000001")

        added_objects: list = []

        def capture_add(obj):
            added_objects.append(obj)

        db = AsyncMock()
        db.add = MagicMock(side_effect=capture_add)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        mock_plan = MagicMock()
        mock_plan.id = plan_id
        mock_plan.is_active = True
        mock_plan.razorpay_plan_id = "plan_rzp_001"  # plan IS linked to Razorpay

        plan_result = MagicMock()
        plan_result.scalar_one_or_none = MagicMock(return_value=mock_plan)
        no_sub_result = MagicMock()
        no_sub_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(side_effect=[plan_result, no_sub_result])

        fake_rzp_sub = {"id": "sub_rzp_test001", "short_url": "https://rzp.io/i/test"}

        from app.core import razorpay as rzp_module

        with (
            patch.object(config.settings, "razorpay_key_id", "rzp_test_key"),
            patch.object(rzp_module, "create_subscription", AsyncMock(return_value=fake_rzp_sub)),
        ):
            result = await start_or_update_subscription(db, tenant_id, plan_id)

        # A new Subscription must have been added
        assert len(added_objects) == 1, f"Expected db.add called once, got {len(added_objects)}"
        new_sub = added_objects[0]

        # Status must be 'trialing', not 'active' (webhook sets active in real mode)
        assert new_sub.status != "active", (
            f"Real mode must NOT set status='active' without a webhook, got {new_sub.status}"
        )
        assert new_sub.status == "trialing", (
            f"Expected status='trialing' for new real-mode sub, got {new_sub.status}"
        )
        assert result.get("payment_required") is True, (
            "Real mode must return payment_required=True"
        )
        assert result.get("razorpay_subscription_id") == "sub_rzp_test001"
        assert result.get("short_url") == "https://rzp.io/i/test"


class TestSubscribeSimulatedMode:
    """Branch 2: when Razorpay is not configured or plan has no razorpay_plan_id,
    the upgrade activates immediately (status='active') with payment_required=False."""

    @pytest.mark.asyncio
    async def test_simulated_no_razorpay_key_activates_immediately(self):
        """Branch 2a: razorpay_key_id is empty → immediate activation, no Razorpay call."""
        import uuid as uuid_mod
        from unittest.mock import AsyncMock, MagicMock, patch

        from app.core import config
        from app.services.subscription_service import start_or_update_subscription

        plan_id = uuid_mod.UUID("00000000-0000-0000-0000-000000000010")
        tenant_id = uuid_mod.UUID("00000000-0000-0000-0000-000000000001")

        added_objects: list = []

        def capture_add(obj):
            added_objects.append(obj)

        db = AsyncMock()
        db.add = MagicMock(side_effect=capture_add)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        mock_plan = MagicMock()
        mock_plan.id = plan_id
        mock_plan.is_active = True
        mock_plan.razorpay_plan_id = "plan_rzp_001"  # plan has rzp id, but no key

        plan_result = MagicMock()
        plan_result.scalar_one_or_none = MagicMock(return_value=mock_plan)
        no_sub_result = MagicMock()
        no_sub_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(side_effect=[plan_result, no_sub_result])

        from app.core import razorpay as rzp_module

        rzp_call = AsyncMock()

        with (
            patch.object(config.settings, "razorpay_key_id", ""),  # no key = simulated
            patch.object(rzp_module, "create_subscription", rzp_call),
        ):
            result = await start_or_update_subscription(db, tenant_id, plan_id)

        assert len(added_objects) == 1, f"Expected db.add called once, got {len(added_objects)}"
        new_sub = added_objects[0]

        assert new_sub.status == "active", (
            f"Simulated mode must set status='active', got {new_sub.status}"
        )
        assert new_sub.plan_id == plan_id, (
            f"plan_id must be the chosen plan, got {new_sub.plan_id}"
        )
        assert result.get("payment_required") is False, (
            "Simulated mode must return payment_required=False"
        )
        assert result.get("razorpay_subscription_id") is None
        assert result.get("short_url") is None
        # No Razorpay API call must be made
        rzp_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_simulated_no_plan_razorpay_id_activates_immediately(self):
        """Branch 2b: razorpay_key_id is set but plan.razorpay_plan_id is None
        (seeded/free plan) → immediate activation, no Razorpay call, plan_id updated."""
        import uuid as uuid_mod
        from unittest.mock import AsyncMock, MagicMock, patch

        from app.core import config
        from app.services.subscription_service import start_or_update_subscription

        plan_id = uuid_mod.UUID("00000000-0000-0000-0000-000000000020")
        tenant_id = uuid_mod.UUID("00000000-0000-0000-0000-000000000001")

        added_objects: list = []

        def capture_add(obj):
            added_objects.append(obj)

        db = AsyncMock()
        db.add = MagicMock(side_effect=capture_add)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        mock_plan = MagicMock()
        mock_plan.id = plan_id
        mock_plan.is_active = True
        mock_plan.razorpay_plan_id = None  # seeded plan has no razorpay_plan_id

        plan_result = MagicMock()
        plan_result.scalar_one_or_none = MagicMock(return_value=mock_plan)
        no_sub_result = MagicMock()
        no_sub_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(side_effect=[plan_result, no_sub_result])

        from app.core import razorpay as rzp_module

        rzp_call = AsyncMock()

        with (
            patch.object(config.settings, "razorpay_key_id", "rzp_test_key"),  # key present
            patch.object(rzp_module, "create_subscription", rzp_call),
        ):
            result = await start_or_update_subscription(db, tenant_id, plan_id)

        assert len(added_objects) == 1, f"Expected db.add called once, got {len(added_objects)}"
        new_sub = added_objects[0]

        assert new_sub.status == "active", (
            f"No-razorpay-plan-id must set status='active', got {new_sub.status}"
        )
        assert new_sub.plan_id == plan_id, (
            f"plan_id must be set to {plan_id}, got {new_sub.plan_id}"
        )
        assert result.get("payment_required") is False
        assert result.get("razorpay_subscription_id") is None
        rzp_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_simulated_upgrade_existing_sub_sets_active_and_plan(self):
        """Branch 2: upgrading an existing subscription (not new) also sets status='active'
        and updates plan_id in simulated mode."""
        import uuid as uuid_mod
        from unittest.mock import AsyncMock, MagicMock, patch

        from app.core import config
        from app.services.subscription_service import start_or_update_subscription

        old_plan_id = uuid_mod.UUID("00000000-0000-0000-0000-000000000010")
        new_plan_id = uuid_mod.UUID("00000000-0000-0000-0000-000000000020")
        tenant_id = uuid_mod.UUID("00000000-0000-0000-0000-000000000001")

        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        mock_plan = MagicMock()
        mock_plan.id = new_plan_id
        mock_plan.is_active = True
        mock_plan.razorpay_plan_id = None  # simulated

        # Existing subscription on the old plan
        existing_sub = MagicMock()
        existing_sub.plan_id = old_plan_id
        existing_sub.status = "trialing"
        existing_sub.razorpay_subscription_id = None

        plan_result = MagicMock()
        plan_result.scalar_one_or_none = MagicMock(return_value=mock_plan)
        sub_result = MagicMock()
        sub_result.scalar_one_or_none = MagicMock(return_value=existing_sub)
        db.execute = AsyncMock(side_effect=[plan_result, sub_result])

        from app.core import razorpay as rzp_module

        rzp_call = AsyncMock()

        with (
            patch.object(config.settings, "razorpay_key_id", ""),
            patch.object(rzp_module, "create_subscription", rzp_call),
        ):
            try:
                result = await start_or_update_subscription(db, tenant_id, new_plan_id)
            except Exception:
                result = {}

        # plan_id on the existing sub must be updated
        assert existing_sub.plan_id == new_plan_id, (
            f"plan_id must be updated to {new_plan_id}, got {existing_sub.plan_id}"
        )
        # status must be set to active in simulated mode
        assert existing_sub.status == "active", (
            f"Simulated upgrade must set status='active', got {existing_sub.status}"
        )
        assert result.get("payment_required") is False
        rzp_call.assert_not_called()


# ---------------------------------------------------------------------------
# 9. Invoice download — invoice.paid webhook upsert + GET /billing/invoices auth
# ---------------------------------------------------------------------------

class TestInvoicePaidWebhook:
    """invoice.paid webhook creates/updates an Invoice row with correct fields."""

    @pytest.mark.asyncio
    async def test_invoice_paid_creates_invoice_row(self):
        """_upsert_invoice creates a new Invoice with correct amount, pdf_url, status."""
        from decimal import Decimal
        from unittest.mock import AsyncMock, MagicMock

        from app.services.subscription_service import _upsert_invoice

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

        # Simulate no existing invoice found (create path).
        no_row = MagicMock()
        no_row.scalar_one_or_none = MagicMock(return_value=None)

        created_invoices = []

        def capture_add(obj):
            created_invoices.append(obj)

        db = AsyncMock()
        db.add = MagicMock(side_effect=capture_add)
        db.execute = AsyncMock(return_value=no_row)

        inv_entity = {
            "id": "inv_test_001",
            "amount": 118000,        # 1180.00 INR in paise
            "tax_amount": 18000,     # 180.00 INR GST in paise
            "short_url": "https://rzp.io/i/test",
            "payment_id": "pay_test_abc",
            "issued_at": 1748649600,  # some epoch
            "paid_at": 1748649700,
        }

        await _upsert_invoice(db, inv_entity, tenant_id)

        assert len(created_invoices) == 1
        inv = created_invoices[0]
        assert inv.razorpay_invoice_id == "inv_test_001"
        assert inv.amount_inr == Decimal("1180.00")
        assert inv.gst_inr == Decimal("180.00")
        assert inv.status == "paid"
        assert inv.pdf_url == "https://rzp.io/i/test"
        assert inv.razorpay_payment_id == "pay_test_abc"
        assert inv.tenant_id == tenant_id
        assert inv.paid_at is not None

    @pytest.mark.asyncio
    async def test_invoice_paid_updates_existing_row(self):
        """_upsert_invoice updates in place when razorpay_invoice_id already exists."""
        from decimal import Decimal
        from unittest.mock import AsyncMock, MagicMock

        from app.services.subscription_service import _upsert_invoice

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

        # Simulate an existing Invoice row (update path).
        existing_inv = MagicMock()
        existing_inv.razorpay_invoice_id = "inv_existing_001"

        existing_row = MagicMock()
        existing_row.scalar_one_or_none = MagicMock(return_value=existing_inv)

        db = AsyncMock()
        db.add = MagicMock()
        db.execute = AsyncMock(return_value=existing_row)

        inv_entity = {
            "id": "inv_existing_001",
            "amount": 59000,
            "tax_amount": 9000,
            "short_url": "https://rzp.io/i/updated",
            "payment_id": "pay_updated",
            "issued_at": 1748649600,
            "paid_at": 1748649800,
        }

        await _upsert_invoice(db, inv_entity, tenant_id)

        # db.add must NOT be called — we updated in place.
        db.add.assert_not_called()
        assert existing_inv.amount_inr == Decimal("590.00")
        assert existing_inv.gst_inr == Decimal("90.00")
        assert existing_inv.status == "paid"
        assert existing_inv.pdf_url == "https://rzp.io/i/updated"
        assert existing_inv.razorpay_payment_id == "pay_updated"

    @pytest.mark.asyncio
    async def test_invoice_paid_no_tenant_skips(self):
        """_upsert_invoice skips upsert if tenant_id cannot be resolved."""
        from unittest.mock import AsyncMock, MagicMock

        from app.services.subscription_service import _upsert_invoice

        no_row = MagicMock()
        no_row.scalar_one_or_none = MagicMock(return_value=None)

        db = AsyncMock()
        db.add = MagicMock()
        db.execute = AsyncMock(return_value=no_row)

        inv_entity = {
            "id": "inv_no_tenant_001",
            "amount": 59000,
            "tax_amount": 0,
        }
        # Pass tenant_id=None and no notes/subscription_id — should skip silently.
        await _upsert_invoice(db, inv_entity, tenant_id=None)

        db.add.assert_not_called()


@pytest.mark.asyncio
async def test_list_invoices_endpoint_requires_auth():
    """GET /billing/invoices must return 401 without a bearer token."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/billing/invoices")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


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


# ---------------------------------------------------------------------------
# 10. Platform analytics endpoint — auth guard + service shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/platform/analytics"),
])
async def test_platform_analytics_requires_auth(method, path):
    """GET /platform/analytics must return 401 without a bearer token."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await getattr(ac, method)(path)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


class TestGetAnalyticsService:
    """Service-level test for platform_service.get_analytics — stubs all DB calls."""

    def _make_db(self, tenant_row, sub_rows, tier_rows, mrr_row):
        """Build an AsyncMock DB that returns the given aggregate rows in order."""
        from unittest.mock import AsyncMock, MagicMock

        def _result(row):
            r = MagicMock()
            r.one = MagicMock(return_value=row)
            r.all = MagicMock(return_value=row if isinstance(row, list) else [row])
            return r

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[
            _result(tenant_row),
            _result(sub_rows),
            _result(tier_rows),
            _result(mrr_row),
        ])
        return db

    @pytest.mark.asyncio
    async def test_analytics_shape_and_types(self):
        """get_analytics returns a PlatformAnalytics with correct types."""
        from decimal import Decimal
        from unittest.mock import AsyncMock, MagicMock

        import app.services.platform_service as ps
        from app.schemas.billing import PlatformAnalytics

        # --- tenant counts row ---
        tenant_row = MagicMock()
        tenant_row.total = 5
        tenant_row.active = 4
        tenant_row.suspended = 1

        # --- subscription status rows ---
        def _sub_row(status, cnt):
            r = MagicMock()
            r.status = status
            r.cnt = cnt
            return r

        sub_rows = [_sub_row("active", 3), _sub_row("trialing", 1), _sub_row("cancelled", 1)]

        # --- tier rows ---
        def _tier_row(tier, cnt):
            r = MagicMock()
            r.tier = tier
            r.cnt = cnt
            return r

        tier_rows = [_tier_row("starter", 2), _tier_row("professional", 1)]

        # --- MRR row ---
        mrr_row = MagicMock()
        mrr_row.mrr = Decimal("2997.00")

        db = AsyncMock()

        # db.execute is called 4 times: tenant_counts, sub_status, tier, mrr
        # Each query uses a different result accessor (.one() for counts, .all() for groups)
        def _result_one(row):
            r = MagicMock()
            r.one = MagicMock(return_value=row)
            return r

        def _result_all(rows):
            r = MagicMock()
            r.all = MagicMock(return_value=rows)
            return r

        db.execute = AsyncMock(side_effect=[
            _result_one(tenant_row),
            _result_all(sub_rows),
            _result_all(tier_rows),
            _result_one(mrr_row),
        ])

        result = await ps.get_analytics(db)

        # Verify the return type is PlatformAnalytics
        assert isinstance(result, PlatformAnalytics)

        # Tenant counts
        assert result.tenants.total == 5
        assert result.tenants.active == 4
        assert result.tenants.suspended == 1

        # Subscription breakdown dict
        assert result.subscriptions["active"] == 3
        assert result.subscriptions["trialing"] == 1
        assert result.subscriptions["cancelled"] == 1

        # By-tier list
        assert len(result.by_tier) == 2
        assert result.by_tier[0].tier == "starter"
        assert result.by_tier[0].count == 2
        assert result.by_tier[1].tier == "professional"
        assert result.by_tier[1].count == 1

        # MRR as string
        assert result.mrr_inr == "2997.00"
        assert isinstance(result.mrr_inr, str)

    @pytest.mark.asyncio
    async def test_analytics_empty_db(self):
        """get_analytics handles a fresh DB with zero rows gracefully."""
        from decimal import Decimal
        from unittest.mock import AsyncMock, MagicMock

        import app.services.platform_service as ps
        from app.schemas.billing import PlatformAnalytics

        tenant_row = MagicMock()
        tenant_row.total = 0
        tenant_row.active = 0
        tenant_row.suspended = 0

        mrr_row = MagicMock()
        mrr_row.mrr = Decimal(0)

        def _result_one(row):
            r = MagicMock()
            r.one = MagicMock(return_value=row)
            return r

        def _result_all(rows):
            r = MagicMock()
            r.all = MagicMock(return_value=rows)
            return r

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[
            _result_one(tenant_row),
            _result_all([]),   # no subscription status rows
            _result_all([]),   # no tier rows
            _result_one(mrr_row),
        ])

        result = await ps.get_analytics(db)

        assert isinstance(result, PlatformAnalytics)
        assert result.tenants.total == 0
        assert result.subscriptions == {}
        assert result.by_tier == []
        assert result.mrr_inr == "0"


# ---------------------------------------------------------------------------
# 11. Subscription lifecycle — cancel / pause / resume (service + endpoint auth)
# ---------------------------------------------------------------------------

def _make_sub(
    tenant_id: uuid.UUID,
    status: str = "active",
    cancel_at_period_end: bool = False,
    rzp_sub_id: str | None = None,
) -> MagicMock:
    """Build a mock Subscription row."""
    sub = MagicMock()
    sub.id = uuid.UUID("00000000-0000-0000-0000-000000000050")
    sub.tenant_id = tenant_id
    sub.plan_id = uuid.UUID("00000000-0000-0000-0000-000000000010")
    sub.status = status
    sub.cancel_at_period_end = cancel_at_period_end
    sub.razorpay_subscription_id = rzp_sub_id
    sub.trial_ends_at = None
    sub.current_period_start = None
    sub.current_period_end = None
    sub.created_at = None
    sub.updated_at = None
    return sub


def _mock_db_with_sub(sub: MagicMock) -> AsyncMock:
    """Return an AsyncMock DB whose execute returns the given subscription."""
    sub_result = MagicMock()
    sub_result.scalar_one_or_none = MagicMock(return_value=sub)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=sub_result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _mock_db_no_sub() -> AsyncMock:
    """Return an AsyncMock DB that returns no subscription row."""
    no_result = MagicMock()
    no_result.scalar_one_or_none = MagicMock(return_value=None)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=no_result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


class TestCancelSubscription:
    """cancel_subscription — demo mode (no Razorpay)."""

    @pytest.mark.asyncio
    async def test_cancel_demo_sets_cancelled_and_flag(self):
        """Demo: no Razorpay key → status='cancelled', cancel_at_period_end=True."""
        from unittest.mock import patch

        from app.core import config
        from app.services.subscription_service import cancel_subscription

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        sub = _make_sub(tenant_id, status="active")
        db = _mock_db_with_sub(sub)

        with patch.object(config.settings, "razorpay_key_id", ""):
            result = await cancel_subscription(db, tenant_id)

        assert result.status == "cancelled"
        assert result.cancel_at_period_end is True
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_no_subscription_raises_not_found(self):
        """cancel_subscription raises AppError(not_found) when no sub exists."""
        from app.services.subscription_service import cancel_subscription

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        db = _mock_db_no_sub()

        with pytest.raises(AppError) as exc:
            await cancel_subscription(db, tenant_id)
        assert exc.value.code.value == "not_found"

    @pytest.mark.asyncio
    async def test_cancel_real_razorpay_sets_flag_not_cancelled(self):
        """Real Razorpay: cancel_at_period_end=True but status stays ('active')."""
        from unittest.mock import AsyncMock, patch

        from app.core import config
        from app.core import razorpay as rzp_module
        from app.services.subscription_service import cancel_subscription

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        sub = _make_sub(tenant_id, status="active", rzp_sub_id="sub_rzp_test001")
        db = _mock_db_with_sub(sub)

        with (
            patch.object(config.settings, "razorpay_key_id", "rzp_test_key"),
            patch.object(rzp_module, "_post", AsyncMock(return_value={})),
        ):
            result = await cancel_subscription(db, tenant_id)

        # Status must NOT be forced to 'cancelled' (webhook does that)
        assert result.status == "active"
        assert result.cancel_at_period_end is True

    @pytest.mark.asyncio
    async def test_cancel_real_razorpay_api_failure_is_non_fatal(self):
        """Real Razorpay: API failure is best-effort — sub still gets cancel_at_period_end."""
        from unittest.mock import patch

        from app.core import config
        from app.core import razorpay as rzp_module
        from app.core.errors import AppError as AE
        from app.core.errors import ErrorCode
        from app.services.subscription_service import cancel_subscription

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        sub = _make_sub(tenant_id, status="active", rzp_sub_id="sub_rzp_test001")
        db = _mock_db_with_sub(sub)

        def _fail(*a, **kw):
            raise AE(ErrorCode.upstream_error, "Razorpay timeout")

        with (
            patch.object(config.settings, "razorpay_key_id", "rzp_test_key"),
            patch.object(rzp_module, "_post", AsyncMock(side_effect=_fail)),
        ):
            # Must not raise — failure is logged, not propagated
            result = await cancel_subscription(db, tenant_id)

        assert result.cancel_at_period_end is True


class TestPauseSubscription:
    """pause_subscription sets status='paused'."""

    @pytest.mark.asyncio
    async def test_pause_sets_paused(self):
        from app.services.subscription_service import pause_subscription

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        sub = _make_sub(tenant_id, status="active")
        db = _mock_db_with_sub(sub)

        result = await pause_subscription(db, tenant_id)

        assert result.status == "paused"
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_no_subscription_raises_not_found(self):
        from app.services.subscription_service import pause_subscription

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        db = _mock_db_no_sub()

        with pytest.raises(AppError) as exc:
            await pause_subscription(db, tenant_id)
        assert exc.value.code.value == "not_found"


class TestResumeSubscription:
    """resume_subscription clears cancel flag and reactivates cancelled/paused."""

    @pytest.mark.asyncio
    async def test_resume_after_cancel_sets_active_and_clears_flag(self):
        from app.services.subscription_service import resume_subscription

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        sub = _make_sub(tenant_id, status="cancelled", cancel_at_period_end=True)
        db = _mock_db_with_sub(sub)

        result = await resume_subscription(db, tenant_id)

        assert result.status == "active"
        assert result.cancel_at_period_end is False
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_resume_after_pause_sets_active(self):
        from app.services.subscription_service import resume_subscription

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        sub = _make_sub(tenant_id, status="paused")
        db = _mock_db_with_sub(sub)

        result = await resume_subscription(db, tenant_id)

        assert result.status == "active"
        assert result.cancel_at_period_end is False

    @pytest.mark.asyncio
    async def test_resume_active_with_pending_cancel_clears_flag(self):
        """Resuming an 'active' sub with cancel_at_period_end=True just clears the flag."""
        from app.services.subscription_service import resume_subscription

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        sub = _make_sub(tenant_id, status="active", cancel_at_period_end=True)
        db = _mock_db_with_sub(sub)

        result = await resume_subscription(db, tenant_id)

        assert result.status == "active"
        assert result.cancel_at_period_end is False

    @pytest.mark.asyncio
    async def test_resume_no_subscription_raises_not_found(self):
        from app.services.subscription_service import resume_subscription

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        db = _mock_db_no_sub()

        with pytest.raises(AppError) as exc:
            await resume_subscription(db, tenant_id)
        assert exc.value.code.value == "not_found"


# Endpoint auth guards for the three new routes
@pytest.mark.asyncio
@pytest.mark.parametrize("path", [
    "/api/v1/billing/cancel",
    "/api/v1/billing/pause",
    "/api/v1/billing/resume",
])
async def test_lifecycle_endpoints_require_auth(path):
    """POST billing/cancel|pause|resume must return 401 without a bearer token."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(path)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 12. Usage / metering — GET /billing/usage
# ---------------------------------------------------------------------------

class TestGetUsageService:
    """Service-level tests for usage_service.get_usage — stubs all DB calls."""

    def _make_db(
        self,
        sub=None,
        plan=None,
        policies_count: int = 0,
        users_count: int = 0,
        documents_count: int = 0,
        alerts_count: int = 0,
    ) -> AsyncMock:
        """Build an AsyncMock DB whose execute calls return the given stubs in order.

        Call sequence inside get_usage:
          1. SELECT Subscription WHERE tenant_id = ?
          2. SELECT Plan WHERE id = ?  (only when sub exists and has plan_id)
          3. get_entitlements (re-enters: SELECT Subscription, then optionally SELECT Plan)
          4. COUNT policies
          5. COUNT profiles (users)
          6. COUNT policy_documents
          7. COUNT alerts
        """

        def _scalar_result(val):
            r = MagicMock()
            r.scalar_one_or_none = MagicMock(return_value=val)
            r.scalar_one = MagicMock(return_value=val)
            return r

        db = AsyncMock()
        # Build the call sequence for db.execute:
        # get_usage owns calls 1-2 (sub + plan for tier); get_entitlements re-queries (calls 3-4);
        # then the 4 COUNT queries.
        calls = []

        # call 1: sub lookup in get_usage
        calls.append(_scalar_result(sub))
        # call 2: plan lookup for tier in get_usage (only when sub has plan_id)
        has_plan_id = getattr(sub, "plan_id", None) is not None
        not_trialing = sub is not None and sub.status != "trialing"
        if sub is not None and has_plan_id and not_trialing:
            calls.append(_scalar_result(plan))
        # calls for get_entitlements (re-queries sub and optionally plan)
        calls.append(_scalar_result(sub))  # sub lookup inside get_entitlements
        ents_has_plan = (
            sub is not None
            and sub.status not in ("trialing", "cancelled", "expired")
            and has_plan_id
        )
        if ents_has_plan:
            calls.append(_scalar_result(plan))  # plan lookup inside get_entitlements
        # COUNT queries
        calls.append(_scalar_result(policies_count))
        calls.append(_scalar_result(users_count))
        calls.append(_scalar_result(documents_count))
        calls.append(_scalar_result(alerts_count))

        db.execute = AsyncMock(side_effect=calls)
        return db

    @pytest.mark.asyncio
    async def test_free_tier_returns_correct_limits(self):
        """No subscription → free-tier limits; usage zeros come through."""
        from app.services.usage_service import get_usage

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        db = self._make_db(
            sub=None, policies_count=3, users_count=1, documents_count=5, alerts_count=10
        )

        result = await get_usage(db, tenant_id)

        assert result.plan_tier == "free"
        assert result.status == "none"
        assert result.usage["policies"].used == 3
        assert result.usage["policies"].limit == 10       # FREE: 10
        assert result.usage["users"].used == 1
        assert result.usage["users"].limit == 1           # FREE: 1
        assert result.usage["documents"].used == 5
        assert result.usage["documents"].limit == 20      # FREE: 20
        assert result.usage["alerts_month"].used == 10
        assert result.usage["alerts_month"].limit == 200  # FREE: 200

    @pytest.mark.asyncio
    async def test_trialing_returns_pro_limits(self):
        """Trialing sub → plan_tier='trialing', Pro-level limits (unlimited for policies)."""
        from app.services.usage_service import get_usage

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

        sub = MagicMock()
        sub.status = "trialing"
        sub.plan_id = None
        sub.tenant_id = tenant_id

        db = self._make_db(
            sub=sub, policies_count=50, users_count=5,
            documents_count=100, alerts_count=300,
        )

        result = await get_usage(db, tenant_id)

        assert result.plan_tier == "trialing"
        assert result.status == "trialing"
        assert result.usage["policies"].used == 50
        assert result.usage["policies"].limit == -1       # PRO: unlimited
        assert result.usage["users"].used == 5
        assert result.usage["users"].limit == 15          # PRO: 15
        assert result.usage["documents"].limit == -1      # PRO: unlimited
        assert result.usage["alerts_month"].limit == -1   # PRO: unlimited

    @pytest.mark.asyncio
    async def test_active_plan_returns_plan_limits(self):
        """Active sub with a linked plan → limits from plan.entitlements."""
        from app.services.usage_service import get_usage

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        plan_id = uuid.UUID("00000000-0000-0000-0000-000000000010")

        sub = MagicMock()
        sub.status = "active"
        sub.plan_id = plan_id
        sub.tenant_id = tenant_id

        mock_plan = MagicMock()
        mock_plan.id = plan_id
        mock_plan.tier = "starter"
        mock_plan.is_active = True
        mock_plan.entitlements = {
            "features": {"email_alerts": True},
            "limits": {"policies": 100, "users": 3, "alerts_month": 500, "documents": 200},
        }

        db = self._make_db(
            sub=sub, plan=mock_plan,
            policies_count=20, users_count=2, documents_count=40, alerts_count=50,
        )

        result = await get_usage(db, tenant_id)

        assert result.plan_tier == "starter"
        assert result.status == "active"
        assert result.usage["policies"].used == 20
        assert result.usage["policies"].limit == 100
        assert result.usage["users"].used == 2
        assert result.usage["users"].limit == 3
        assert result.usage["documents"].used == 40
        assert result.usage["documents"].limit == 200
        assert result.usage["alerts_month"].used == 50
        assert result.usage["alerts_month"].limit == 500

    @pytest.mark.asyncio
    async def test_unlimited_limit_passes_through_as_minus_one(self):
        """Plans with -1 limit pass through correctly (unlimited entitlements)."""
        from app.services.usage_service import get_usage

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        plan_id = uuid.UUID("00000000-0000-0000-0000-000000000020")

        sub = MagicMock()
        sub.status = "active"
        sub.plan_id = plan_id
        sub.tenant_id = tenant_id

        mock_plan = MagicMock()
        mock_plan.id = plan_id
        mock_plan.tier = "professional"
        mock_plan.is_active = True
        mock_plan.entitlements = {
            "features": {},
            "limits": {"policies": -1, "users": 15, "alerts_month": -1, "documents": -1},
        }

        db = self._make_db(
            sub=sub, plan=mock_plan,
            policies_count=999, users_count=14, documents_count=5000, alerts_count=9999,
        )

        result = await get_usage(db, tenant_id)

        assert result.usage["policies"].limit == -1
        assert result.usage["documents"].limit == -1
        assert result.usage["alerts_month"].limit == -1
        assert result.usage["users"].limit == 15   # explicit numeric limit passes through

    @pytest.mark.asyncio
    async def test_cancelled_sub_falls_back_to_free(self):
        """Cancelled subscription → plan_tier='free', free limits apply."""
        from app.services.usage_service import get_usage

        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

        sub = MagicMock()
        sub.status = "cancelled"
        sub.plan_id = uuid.UUID("00000000-0000-0000-0000-000000000010")
        sub.tenant_id = tenant_id

        db = self._make_db(
            sub=sub, policies_count=1, users_count=1, documents_count=1, alerts_count=1
        )

        result = await get_usage(db, tenant_id)

        assert result.status == "cancelled"
        assert result.plan_tier == "free"
        assert result.usage["policies"].limit == 10


@pytest.mark.asyncio
async def test_usage_endpoint_requires_auth():
    """GET /billing/usage must return 401 without a bearer token."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/billing/usage")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"
