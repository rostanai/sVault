"""Claims module tests.

Coverage
--------
1. Endpoint auth guards — every claims route returns 401 without a bearer token.
   Uses a local FastAPI test app (the claims router is not yet wired into the main
   app router.py — see the report for the line to add).
2. Service-layer unit tests (mock DB):
   a. create() writes an initial ClaimEvent with event_type="status_change".
   b. update() with a status change writes a ClaimEvent with from_status / to_status.
   c. update() with no status change but a note writes a "note" event.
3. Object-level isolation (real in-memory SQLite):
   - Owner A cannot get / list / patch a claim on Owner B's policy (→ 404).
   - Manager sees claims for both owners.
   - Cross-tenant claim → 404.
4. list_claims returns empty for a user with no tenant_id (no DB call).
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import ARRAY
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql.named_types import ENUM as PGENUM
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles

import app.db.models  # noqa: F401 — registers all ORM tables on Base.metadata
from app.api.v1 import claims as claims_module
from app.core.errors import AppError, register_error_handlers
from app.core.security import CurrentUser
from app.db.base import Base
from app.db.models import Organization, Policy, Profile, Tenant
from app.db.models.claims import Claim, ClaimEvent
from app.schemas.claim import ClaimCreate, ClaimUpdate
from app.services import claim_service

# ---------------------------------------------------------------------------
# Minimal ASGI app that mounts only the claims router — used for auth-guard tests.
# This avoids depending on router.py being updated before these tests pass.
# ---------------------------------------------------------------------------
_test_app = FastAPI()
register_error_handlers(_test_app)
_test_app.include_router(claims_module.router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# SQLite DDL shims (identical to test_object_level_access.py)
# ---------------------------------------------------------------------------

@compiles(JSONB, "sqlite")
def _compile_jsonb(type_, compiler, **kw):  # noqa: ARG001
    return "JSON"


@compiles(PGENUM, "sqlite")
def _compile_enum(type_, compiler, **kw):  # noqa: ARG001
    return "VARCHAR"


@compiles(PG_ARRAY, "sqlite")
@compiles(ARRAY, "sqlite")
def _compile_array(type_, compiler, **kw):  # noqa: ARG001
    return "JSON"


# ---------------------------------------------------------------------------
# Stable IDs
# ---------------------------------------------------------------------------

TENANT_ID = uuid.uuid4()
ORG_ID = uuid.uuid4()
USER_A = uuid.uuid4()
USER_B = uuid.uuid4()
USER_M = uuid.uuid4()
POLICY_A = uuid.uuid4()
POLICY_B = uuid.uuid4()
CLAIM_A = uuid.uuid4()
CLAIM_B = uuid.uuid4()

OTHER_TENANT = uuid.uuid4()
OTHER_ORG = uuid.uuid4()
OTHER_USER = uuid.uuid4()
OTHER_POLICY = uuid.uuid4()
OTHER_CLAIM = uuid.uuid4()


def _u(
    user_id: uuid.UUID,
    role: str,
    *,
    tenant: uuid.UUID = TENANT_ID,
    org: uuid.UUID = ORG_ID,
    super_admin: bool = False,
) -> CurrentUser:
    return CurrentUser(
        user_id=str(user_id),
        tenant_id=str(tenant),
        org_id=str(org),
        role=role,
        is_super_admin=super_admin,
    )


owner_a = _u(USER_A, "owner")
owner_b = _u(USER_B, "owner")
manager = _u(USER_M, "manager")
other_owner = _u(OTHER_USER, "owner", tenant=OTHER_TENANT, org=OTHER_ORG)

# ---------------------------------------------------------------------------
# Tables needed by these tests
# ---------------------------------------------------------------------------

_TABLE_NAMES = [
    "tenants",
    "organizations",
    "profiles",
    "providers",
    "provider_contacts",
    "policies",
    "policy_documents",
    "alerts",
    "alert_rules",
    "policy_installments",
    "approvals",
    "claims",
    "claim_events",
]


@pytest_asyncio.fixture
async def db():
    """Fresh in-memory SQLite DB seeded with two owners, two policies, two claims."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [Base.metadata.tables[n] for n in _TABLE_NAMES]
    async with engine.begin() as conn:
        await conn.run_sync(lambda s: Base.metadata.create_all(s, tables=tables))

    now = datetime.now(UTC)
    today = date.today()

    async with AsyncSession(engine) as session:
        session.add_all([
            Tenant(id=TENANT_ID, name="Acme Group", status="active"),
            Tenant(id=OTHER_TENANT, name="Other Corp", status="active"),
            Organization(id=ORG_ID, tenant_id=TENANT_ID, name="Acme HQ", org_type="parent"),
            Organization(id=OTHER_ORG, tenant_id=OTHER_TENANT, name="Other HQ", org_type="parent"),
            Profile(id=USER_A, tenant_id=TENANT_ID, org_id=ORG_ID, role="owner",
                    email="a@acme.test", full_name="Owner A"),
            Profile(id=USER_B, tenant_id=TENANT_ID, org_id=ORG_ID, role="owner",
                    email="b@acme.test", full_name="Owner B"),
            Profile(id=USER_M, tenant_id=TENANT_ID, org_id=ORG_ID, role="manager",
                    email="m@acme.test", full_name="Manager M"),
            Profile(id=OTHER_USER, tenant_id=OTHER_TENANT, org_id=OTHER_ORG, role="owner",
                    email="o@other.test", full_name="Other Owner"),
        ])
        session.add_all([
            Policy(id=POLICY_A, tenant_id=TENANT_ID, org_id=ORG_ID,
                   category="vehicle", title="Policy A", owner_id=USER_A,
                   status="active", premium_inr=1000, sum_insured_inr=100000,
                   expiry_date=today + timedelta(days=10), custom_fields={}),
            Policy(id=POLICY_B, tenant_id=TENANT_ID, org_id=ORG_ID,
                   category="plant", title="Policy B", owner_id=USER_B,
                   status="active", premium_inr=2000, sum_insured_inr=200000,
                   expiry_date=today + timedelta(days=20), custom_fields={}),
            Policy(id=OTHER_POLICY, tenant_id=OTHER_TENANT, org_id=OTHER_ORG,
                   category="vehicle", title="Other Policy", owner_id=OTHER_USER,
                   status="active", premium_inr=9, sum_insured_inr=9,
                   expiry_date=today + timedelta(days=5), custom_fields={}),
        ])
        session.add_all([
            Claim(id=CLAIM_A, tenant_id=TENANT_ID, org_id=ORG_ID, policy_id=POLICY_A,
                  claim_number="CLM-001", status="reported",
                  created_by=USER_A, created_at=now, updated_at=now),
            Claim(id=CLAIM_B, tenant_id=TENANT_ID, org_id=ORG_ID, policy_id=POLICY_B,
                  claim_number="CLM-002", status="reported",
                  created_by=USER_B, created_at=now, updated_at=now),
            Claim(id=OTHER_CLAIM, tenant_id=OTHER_TENANT, org_id=OTHER_ORG,
                  policy_id=OTHER_POLICY, claim_number="CLM-X", status="reported",
                  created_by=OTHER_USER, created_at=now, updated_at=now),
        ])
        await session.commit()

    async with AsyncSession(engine) as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# 1. Endpoint auth guards — 401 without a bearer token
# ---------------------------------------------------------------------------

NULL_UUID = "00000000-0000-0000-0000-000000000000"


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", [
    ("get",   "/api/v1/claims",                                         None),
    ("post",  "/api/v1/claims",
              {"policy_id": NULL_UUID}),
    ("get",   f"/api/v1/claims/{NULL_UUID}",                            None),
    ("patch", f"/api/v1/claims/{NULL_UUID}",                            {}),
    ("get",   f"/api/v1/claims/{NULL_UUID}/events",                     None),
    ("get",   f"/api/v1/policies/{NULL_UUID}/claims",                   None),
])
async def test_claims_endpoints_require_auth(method: str, path: str, body: dict | None):
    """Every claims endpoint must return 401 without a bearer token."""
    transport = httpx.ASGITransport(app=_test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        kwargs = {"json": body} if body is not None else {}
        resp = await getattr(ac, method)(path, **kwargs)
    assert resp.status_code == 401, f"{method.upper()} {path} should be 401 without auth"
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 2a. create() writes an initial status_change ClaimEvent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_writes_initial_event(db):
    """create() must persist a ClaimEvent(event_type=status_change, from=None, to=status)."""
    payload = ClaimCreate(
        policy_id=POLICY_A,
        claim_number="CLM-NEW",
        status="reported",
        description="Test incident",
    )
    result = await claim_service.create(db, owner_a, payload)

    assert result.claim_number == "CLM-NEW"
    assert result.status == "reported"
    assert result.policy_title == "Policy A"

    # Verify the event was created in the DB.
    from sqlalchemy import select as sa_select
    events_q = await db.execute(
        sa_select(ClaimEvent).where(ClaimEvent.claim_id == result.id)
    )
    events = events_q.scalars().all()
    assert len(events) == 1
    evt = events[0]
    assert evt.event_type == "status_change"
    assert evt.from_status is None
    assert evt.to_status == "reported"
    assert evt.note == "Claim created"


# ---------------------------------------------------------------------------
# 2b. update() with status change writes a status_change ClaimEvent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_status_change_writes_event(db):
    """PATCH that changes status must write a status_change ClaimEvent with from/to."""
    payload = ClaimUpdate(status="under_review", note="Sending to adjuster")
    result = await claim_service.update(db, owner_a, CLAIM_A, payload)

    assert result.status == "under_review"

    from sqlalchemy import select as sa_select
    events_q = await db.execute(
        sa_select(ClaimEvent)
        .where(ClaimEvent.claim_id == CLAIM_A)
        .order_by(ClaimEvent.created_at.desc())
    )
    events = list(events_q.scalars().all())
    assert len(events) >= 1
    evt = events[0]
    assert evt.event_type == "status_change"
    assert evt.from_status == "reported"
    assert evt.to_status == "under_review"
    assert evt.note == "Sending to adjuster"


# ---------------------------------------------------------------------------
# 2c. update() without status change but with note writes a "note" event
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_note_only_writes_note_event(db):
    """PATCH with only a note (no status change) must write a ClaimEvent(event_type='note')."""
    payload = ClaimUpdate(note="Additional documents received")
    await claim_service.update(db, owner_a, CLAIM_A, payload)

    from sqlalchemy import select as sa_select
    events_q = await db.execute(
        sa_select(ClaimEvent)
        .where(ClaimEvent.claim_id == CLAIM_A)
        .order_by(ClaimEvent.created_at.desc())
    )
    events = list(events_q.scalars().all())
    evt = events[0]
    assert evt.event_type == "note"
    assert evt.note == "Additional documents received"
    assert evt.from_status is None
    assert evt.to_status is None


# ---------------------------------------------------------------------------
# 3. Object-level isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_owner_a_can_get_own_claim(db):
    result = await claim_service.get_claim(db, owner_a, CLAIM_A)
    assert result.id == CLAIM_A


@pytest.mark.asyncio
async def test_owner_a_cannot_get_owner_b_claim(db):
    """Owner A must get 404 for a claim on Owner B's policy."""
    with pytest.raises(AppError) as exc_info:
        await claim_service.get_claim(db, owner_a, CLAIM_B)
    assert exc_info.value.code.value == "not_found"


@pytest.mark.asyncio
async def test_owner_a_cannot_patch_owner_b_claim(db):
    """Owner A must get 404 when trying to PATCH a claim on Owner B's policy."""
    with pytest.raises(AppError) as exc_info:
        await claim_service.update(db, owner_a, CLAIM_B, ClaimUpdate(status="under_review"))
    assert exc_info.value.code.value == "not_found"


@pytest.mark.asyncio
async def test_owner_a_list_only_own_claims(db):
    """list_claims for Owner A must only return claims on Owner A's policies."""
    results = await claim_service.list_claims(db, owner_a)
    ids = {r.id for r in results}
    assert CLAIM_A in ids
    assert CLAIM_B not in ids
    assert OTHER_CLAIM not in ids


@pytest.mark.asyncio
async def test_owner_b_list_only_own_claims(db):
    """list_claims for Owner B must only return claims on Owner B's policies."""
    results = await claim_service.list_claims(db, owner_b)
    ids = {r.id for r in results}
    assert CLAIM_B in ids
    assert CLAIM_A not in ids
    assert OTHER_CLAIM not in ids


@pytest.mark.asyncio
async def test_manager_sees_all_claims_in_tenant(db):
    """Manager must see claims for both owners (no owner filter)."""
    results = await claim_service.list_claims(db, manager)
    ids = {r.id for r in results}
    assert CLAIM_A in ids
    assert CLAIM_B in ids
    assert OTHER_CLAIM not in ids


@pytest.mark.asyncio
async def test_cross_tenant_claim_not_found_on_get(db):
    """A claim from another tenant must return 404 regardless of role."""
    with pytest.raises(AppError) as exc_info:
        await claim_service.get_claim(db, owner_a, OTHER_CLAIM)
    assert exc_info.value.code.value == "not_found"


@pytest.mark.asyncio
async def test_cross_tenant_claim_not_in_list(db):
    """Cross-tenant claims must never appear in list_claims for any caller."""
    for user in (owner_a, manager):
        results = await claim_service.list_claims(db, user)
        assert OTHER_CLAIM not in {r.id for r in results}


@pytest.mark.asyncio
async def test_owner_a_cannot_list_owner_b_policy_claims(db):
    """list_for_policy on Owner B's policy must return 404 for Owner A."""
    with pytest.raises(AppError) as exc_info:
        await claim_service.list_for_policy(db, owner_a, POLICY_B)
    assert exc_info.value.code.value == "not_found"


@pytest.mark.asyncio
async def test_manager_can_list_any_policy_claims(db):
    """Manager must be able to list claims for both policies."""
    results_a = await claim_service.list_for_policy(db, manager, POLICY_A)
    results_b = await claim_service.list_for_policy(db, manager, POLICY_B)
    assert any(r.id == CLAIM_A for r in results_a)
    assert any(r.id == CLAIM_B for r in results_b)


# ---------------------------------------------------------------------------
# 4. list_claims returns empty for no-tenant user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_claims_no_tenant_returns_empty():
    """A user with no tenant_id must receive an empty list without hitting the DB."""
    user = CurrentUser(user_id="x", tenant_id=None, org_id=None, role="admin")
    db_mock = AsyncMock()
    result = await claim_service.list_claims(db_mock, user)
    assert result == []
    db_mock.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# 5. Segregation of duties — only approver roles may adjudicate a claim
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("bad_status", ["approved", "rejected", "settled"])
async def test_owner_cannot_adjudicate_own_claim(db, bad_status: str):
    """An owner must NOT be able to approve/reject/settle their own claim (SoD)."""
    with pytest.raises(AppError) as exc_info:
        await claim_service.update(db, owner_a, CLAIM_A, ClaimUpdate(status=bad_status))
    assert exc_info.value.code.value == "forbidden"


@pytest.mark.asyncio
async def test_owner_cannot_set_approved_amount(db):
    """An owner must NOT be able to set the approved payout amount (SoD)."""
    with pytest.raises(AppError) as exc_info:
        await claim_service.update(
            db, owner_a, CLAIM_A, ClaimUpdate(approved_amount_inr=50000)
        )
    assert exc_info.value.code.value == "forbidden"


@pytest.mark.asyncio
async def test_owner_can_still_progress_non_adjudication_status(db):
    """SoD must not block ordinary owner updates (e.g. reported → under_review)."""
    result = await claim_service.update(
        db, owner_a, CLAIM_A, ClaimUpdate(status="under_review")
    )
    assert result.status == "under_review"


@pytest.mark.asyncio
async def test_manager_can_approve_and_set_amount(db):
    """A manager (approver) may approve a claim and set the approved amount."""
    result = await claim_service.update(
        db, manager, CLAIM_A,
        ClaimUpdate(status="approved", approved_amount_inr=75000, note="Approved"),
    )
    assert result.status == "approved"
