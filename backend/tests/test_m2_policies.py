"""M2 tests — policy/provider models, scoping logic, endpoint auth guards."""
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.security import CurrentUser
from app.main import app
from app.services.policy_service import _accessible_org_filter


def _user(role: str, super_admin: bool = False) -> CurrentUser:
    return CurrentUser(
        user_id=str(uuid.uuid4()), tenant_id=str(uuid.uuid4()),
        org_id=str(uuid.uuid4()), role=role, is_super_admin=super_admin,
    )


def test_models_include_policy_provider():
    from app.db.models import Policy, PolicyDocument, Provider
    assert Policy.__tablename__ == "policies"
    assert Provider.__tablename__ == "providers"
    assert PolicyDocument.__tablename__ == "policy_documents"


def test_accessible_org_filter_scope():
    # Admin/Manager + super admin -> no org restriction (whole group)
    assert _accessible_org_filter(_user("admin")) is None
    assert _accessible_org_filter(_user("manager")) is None
    assert _accessible_org_filter(_user("viewer", super_admin=True)) is None
    # Owner/Viewer -> restricted to their own org
    owner = _user("owner")
    assert _accessible_org_filter(owner) == uuid.UUID(owner.org_id)
    viewer = _user("viewer")
    assert _accessible_org_filter(viewer) == uuid.UUID(viewer.org_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/policies"),
    ("post", "/api/v1/policies"),
    ("get", "/api/v1/providers"),
    ("post", "/api/v1/providers"),
])
async def test_m2_endpoints_require_auth(method, path):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        kwargs = {"json": {}} if method == "post" else {}
        resp = await getattr(ac, method)(path, **kwargs)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# Renewal endpoint — unit tests (no real DB; service layer mocked)
# ---------------------------------------------------------------------------

def _make_policy_obj(
    *,
    tenant_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
    category: str = "vehicle",
    title: str = "Test Policy",
    policy_number: str | None = "POL-001",
    provider_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    sum_insured_inr: Decimal | None = Decimal("1000000.00"),
    premium_inr: Decimal | None = Decimal("25000.00"),
    gst_inr: Decimal | None = Decimal("4500.00"),
    inception_date: date | None = date(2025, 4, 1),
    expiry_date: date | None = date(2026, 3, 31),
    renewal_date: date | None = date(2026, 3, 1),
    status: str = "active",
    prev_policy_id: uuid.UUID | None = None,
    custom_fields: dict | None = None,
) -> MagicMock:
    from datetime import datetime
    pol = MagicMock()
    pol.id = uuid.uuid4()
    pol.tenant_id = tenant_id or uuid.uuid4()
    pol.org_id = org_id or uuid.uuid4()
    pol.category = category
    pol.title = title
    pol.policy_number = policy_number
    pol.provider_id = provider_id
    pol.owner_id = owner_id
    pol.sum_insured_inr = sum_insured_inr
    pol.premium_inr = premium_inr
    pol.gst_inr = gst_inr
    pol.inception_date = inception_date
    pol.expiry_date = expiry_date
    pol.renewal_date = renewal_date
    pol.status = status
    pol.prev_policy_id = prev_policy_id
    pol.custom_fields = custom_fields or {}
    pol.created_at = datetime(2025, 4, 1, 0, 0, 0)
    return pol


@pytest.mark.asyncio
async def test_renew_creates_new_policy_with_correct_linkage():
    """renew() must return a new Policy whose prev_policy_id == source.id, status active,
    new expiry_date, and carry-over fields (title, category, org_id) from source."""
    from app.schemas.policy import RenewPolicyRequest
    from app.services import policy_service

    source_policy = _make_policy_obj()
    new_expiry = date(2027, 3, 31)

    # Collect the Policy instance that gets added to the session so we can inspect it.
    added_policies: list = []

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    def _capture_add(obj):
        added_policies.append(obj)

    mock_db.add = _capture_add
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    async def _refresh(obj):
        # Simulate a DB id assignment on the new policy after flush.
        if not hasattr(obj, "_refreshed"):
            obj._refreshed = True
            if hasattr(obj, "prev_policy_id"):  # it's a real Policy ORM instance
                obj.id = uuid.uuid4()

    mock_db.refresh = _refresh

    payload = RenewPolicyRequest(expiry_date=new_expiry)

    with patch.object(policy_service, "get_policy", AsyncMock(return_value=source_policy)):
        await policy_service.renew(mock_db, _user("admin"), source_policy.id, payload)

    # A new Policy should have been added.
    assert len(added_policies) == 1
    new_orm = added_policies[0]

    # Linkage: prev_policy_id points to source.
    assert new_orm.prev_policy_id == source_policy.id

    # Status active.
    assert new_orm.status == "active"

    # New expiry_date applied.
    assert new_orm.expiry_date == new_expiry

    # Carry-over fields preserved.
    assert new_orm.org_id == source_policy.org_id
    assert new_orm.category == source_policy.category
    assert new_orm.title == source_policy.title

    # inception_date defaults to source.expiry_date (continuous cover).
    assert new_orm.inception_date == source_policy.expiry_date

    # Source is marked renewed (mutation happens on the MagicMock via _apply_mark_renewed).
    assert source_policy.status == "renewed"

    # Only one commit (atomic).
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_renew_source_marked_renewed():
    """After renew(), the source policy's status must be 'renewed'."""
    from app.schemas.policy import RenewPolicyRequest
    from app.services import policy_service

    source = _make_policy_obj(status="active")
    mock_db = AsyncMock()
    mock_db.add = lambda _: None
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    payload = RenewPolicyRequest(expiry_date=date(2027, 3, 31))

    with patch.object(policy_service, "get_policy", AsyncMock(return_value=source)):
        await policy_service.renew(mock_db, _user("admin"), source.id, payload)

    assert source.status == "renewed"


@pytest.mark.asyncio
async def test_renew_payload_overrides_are_applied():
    """Optional payload overrides should replace source values on the new policy."""
    from app.schemas.policy import RenewPolicyRequest
    from app.services import policy_service

    source = _make_policy_obj(
        sum_insured_inr=Decimal("1000000.00"),
        premium_inr=Decimal("25000.00"),
        policy_number="POL-001",
    )
    added: list = []
    mock_db = AsyncMock()
    mock_db.add = lambda obj: added.append(obj)
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    new_inception = date(2026, 4, 1)
    payload = RenewPolicyRequest(
        expiry_date=date(2027, 3, 31),
        inception_date=new_inception,
        premium_inr=Decimal("28000.00"),
        sum_insured_inr=Decimal("1200000.00"),
        policy_number="POL-002",
    )

    with patch.object(policy_service, "get_policy", AsyncMock(return_value=source)):
        await policy_service.renew(mock_db, _user("admin"), source.id, payload)

    new_orm = added[0]
    assert new_orm.inception_date == new_inception
    assert new_orm.premium_inr == Decimal("28000.00")
    assert new_orm.sum_insured_inr == Decimal("1200000.00")
    assert new_orm.policy_number == "POL-002"


@pytest.mark.asyncio
async def test_renew_endpoint_requires_auth():
    """POST /policies/{id}/renew must return 401 without a bearer token."""
    policy_id = uuid.uuid4()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            f"/api/v1/policies/{policy_id}/renew",
            json={"expiry_date": "2027-03-31"},
        )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_renew_endpoint_404_cross_tenant():
    """POST /policies/{id}/renew with a valid token but non-existent/cross-tenant policy
    must return 404 (never 403) — existence must not be revealed."""
    from app.core.authz import get_current_user
    from app.core.errors import not_found
    from app.db.session import get_db

    policy_id = uuid.uuid4()
    fake_user = _user("admin")

    # Override get_current_user (stable single reference) so no real JWT is needed.
    app.dependency_overrides[get_current_user] = lambda: fake_user

    # Provide a mock DB session; get_policy raises not_found for cross-tenant access.
    async def _mock_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _mock_db

    transport = httpx.ASGITransport(app=app)
    try:
        with patch(
            "app.services.policy_service.get_policy",
            AsyncMock(side_effect=not_found("Policy not found")),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post(
                    f"/api/v1/policies/{policy_id}/renew",
                    json={"expiry_date": "2027-03-31"},
                )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
