"""Object-level access control for the ``owner`` role (BOLA defence).

The owner role may only see/act on the policies they own
(``policies.owner_id == their user id``) — for reads AND writes, AND everything
derived from policies (documents, installments, alerts, dashboard, reports,
exports, notification feed). Admin / Manager / Viewer / Super-Admin keep full
org/group scope (no object restriction). Tenant + org scoping is unchanged.

These are *behavioural* isolation tests: they run the REAL service code against a
real (in-memory SQLite) database loaded with two owners' data, and assert that an
owner never sees the other owner's rows, while a manager sees both. This is the
critical deliverable — it proves the WHERE filters actually isolate data rather
than merely checking a mock was called.

SQLite is used (no Postgres available in CI). Postgres-only column types
(JSONB / ENUM) are shimmed to JSON / VARCHAR for DDL only; the queries under
test are dialect-agnostic. Full-text-search paths (document_library search,
RAG) are NOT exercised here because they rely on Postgres ``to_tsvector`` — the
owner filter on those paths is covered by the non-search list path which shares
the same JOIN + owner WHERE.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import ARRAY
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql.named_types import ENUM as PGENUM
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles

import app.db.models  # noqa: F401 — registers all ORM tables on Base.metadata
from app.core.errors import AppError
from app.core.security import CurrentUser
from app.db.base import Base
from app.db.models import (
    Alert,
    Organization,
    Policy,
    PolicyDocument,
    Profile,
    Tenant,
)
from app.schemas.policy import PolicyUpdate, RenewPolicyRequest
from app.services import (
    account_export_service,
    alert_service,
    dashboard_service,
    data_io_service,
    document_library_service,
    notification_feed_service,
    policy_service,
)

# ---------------------------------------------------------------------------
# SQLite DDL shims for Postgres-only column types (DDL only; query logic intact)
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
    return "JSON"  # array columns are unused by the queries under test


# Only the tables the services under test touch. (document_chunks is raw-SQL /
# Postgres-FTS-only and is not exercised.)
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
]

# Stable IDs so tests can reference specific rows.
TENANT_ID = uuid.uuid4()
ORG_ID = uuid.uuid4()
USER_A = uuid.uuid4()   # owner A
USER_B = uuid.uuid4()   # owner B
USER_M = uuid.uuid4()   # manager
USER_V = uuid.uuid4()   # viewer
POLICY_A = uuid.uuid4()  # owned by A
POLICY_B = uuid.uuid4()  # owned by B

# A second tenant — for the cross-tenant isolation assertion.
OTHER_TENANT = uuid.uuid4()
OTHER_ORG = uuid.uuid4()
OTHER_USER = uuid.uuid4()
OTHER_POLICY = uuid.uuid4()


def _u(user_id: uuid.UUID, role: str, *, tenant=TENANT_ID, org=ORG_ID,
       super_admin=False) -> CurrentUser:
    return CurrentUser(
        user_id=str(user_id), tenant_id=str(tenant), org_id=str(org),
        role=role, is_super_admin=super_admin,
    )


owner_a = _u(USER_A, "owner")
owner_b = _u(USER_B, "owner")
manager = _u(USER_M, "manager")
viewer = _u(USER_V, "viewer")
super_admin = _u(uuid.uuid4(), "", super_admin=True)
other_owner = _u(OTHER_USER, "owner", tenant=OTHER_TENANT, org=OTHER_ORG)


@pytest_asyncio.fixture
async def db():
    """Fresh in-memory DB seeded with two owners' isolated data + a 2nd tenant."""
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
            Organization(id=ORG_ID, tenant_id=TENANT_ID, name="Acme HQ",
                          org_type="parent"),
            Organization(id=OTHER_ORG, tenant_id=OTHER_TENANT, name="Other HQ",
                         org_type="parent"),
            Profile(id=USER_A, tenant_id=TENANT_ID, org_id=ORG_ID, role="owner",
                    email="a@acme.test", full_name="Owner A"),
            Profile(id=USER_B, tenant_id=TENANT_ID, org_id=ORG_ID, role="owner",
                    email="b@acme.test", full_name="Owner B"),
            Profile(id=USER_M, tenant_id=TENANT_ID, org_id=ORG_ID, role="manager",
                    email="m@acme.test", full_name="Manager M"),
            Profile(id=USER_V, tenant_id=TENANT_ID, org_id=ORG_ID, role="viewer",
                    email="v@acme.test", full_name="Viewer V"),
        ])
        # Two policies in the SAME org, owned by different owners.
        session.add_all([
            Policy(id=POLICY_A, tenant_id=TENANT_ID, org_id=ORG_ID,
                   category="vehicle", title="PA — A's fleet", owner_id=USER_A,
                   status="active", premium_inr=1000, sum_insured_inr=100000,
                   expiry_date=today + timedelta(days=10), custom_fields={}),
            Policy(id=POLICY_B, tenant_id=TENANT_ID, org_id=ORG_ID,
                   category="plant", title="PB — B's plant", owner_id=USER_B,
                   status="active", premium_inr=2000, sum_insured_inr=200000,
                   expiry_date=today + timedelta(days=20), custom_fields={}),
            # Cross-tenant policy (must never be visible to Acme users).
            Policy(id=OTHER_POLICY, tenant_id=OTHER_TENANT, org_id=OTHER_ORG,
                   category="vehicle", title="OTHER", owner_id=OTHER_USER,
                   status="active", premium_inr=9, sum_insured_inr=9,
                   expiry_date=today + timedelta(days=5), custom_fields={}),
        ])
        # One document per policy.
        session.add_all([
            PolicyDocument(id=uuid.uuid4(), tenant_id=TENANT_ID, org_id=ORG_ID,
                           policy_id=POLICY_A, storage_path="t/a.pdf",
                           file_name="a.pdf", doc_type="policy", created_at=now),
            PolicyDocument(id=uuid.uuid4(), tenant_id=TENANT_ID, org_id=ORG_ID,
                           policy_id=POLICY_B, storage_path="t/b.pdf",
                           file_name="b.pdf", doc_type="policy", created_at=now),
        ])
        # One alert per policy.
        session.add_all([
            Alert(id=uuid.uuid4(), tenant_id=TENANT_ID, org_id=ORG_ID,
                  policy_id=POLICY_A, channel="email", lead_day=7,
                  scheduled_for=today, status="scheduled", created_at=now),
            Alert(id=uuid.uuid4(), tenant_id=TENANT_ID, org_id=ORG_ID,
                  policy_id=POLICY_B, channel="email", lead_day=7,
                  scheduled_for=today, status="scheduled", created_at=now),
        ])
        await session.commit()

    async with AsyncSession(engine) as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# Unit: the _owner_filter helper itself
# ---------------------------------------------------------------------------

def test_owner_filter_returns_user_id_for_owner():
    assert policy_service._owner_filter(owner_a) == USER_A


def test_owner_filter_none_for_non_owner_roles():
    assert policy_service._owner_filter(manager) is None
    assert policy_service._owner_filter(viewer) is None
    assert policy_service._owner_filter(_u(uuid.uuid4(), "admin")) is None


def test_owner_filter_none_for_super_admin_even_if_owner_role():
    sa = _u(uuid.uuid4(), "owner", super_admin=True)
    assert policy_service._owner_filter(sa) is None


# ---------------------------------------------------------------------------
# list_policies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_owner_a_lists_only_own_policy(db):
    titles = [p.title for p in await policy_service.list_policies(db, owner_a)]
    assert titles == ["PA — A's fleet"]


@pytest.mark.asyncio
async def test_owner_b_lists_only_own_policy(db):
    titles = [p.title for p in await policy_service.list_policies(db, owner_b)]
    assert titles == ["PB — B's plant"]


@pytest.mark.asyncio
async def test_manager_lists_both_policies(db):
    titles = sorted(p.title for p in await policy_service.list_policies(db, manager))
    assert titles == ["PA — A's fleet", "PB — B's plant"]


@pytest.mark.asyncio
async def test_viewer_lists_both_policies(db):
    titles = sorted(p.title for p in await policy_service.list_policies(db, viewer))
    assert titles == ["PA — A's fleet", "PB — B's plant"]


@pytest.mark.asyncio
async def test_cross_tenant_policy_never_listed(db):
    for user in (owner_a, manager, viewer, super_admin):
        titles = [p.title for p in await policy_service.list_policies(db, user)]
        assert "OTHER" not in titles


# ---------------------------------------------------------------------------
# get_policy + all sub-resources that route through get_policy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_owner_a_get_own_policy_ok(db):
    policy = await policy_service.get_policy(db, owner_a, POLICY_A)
    assert policy.id == POLICY_A


@pytest.mark.asyncio
async def test_owner_a_get_other_owner_policy_404(db):
    with pytest.raises(AppError) as exc:
        await policy_service.get_policy(db, owner_a, POLICY_B)
    assert exc.value.code.value == "not_found"


@pytest.mark.asyncio
async def test_owner_b_get_other_owner_policy_404(db):
    with pytest.raises(AppError):
        await policy_service.get_policy(db, owner_b, POLICY_A)


@pytest.mark.asyncio
async def test_manager_get_either_policy_ok(db):
    assert (await policy_service.get_policy(db, manager, POLICY_A)).id == POLICY_A
    assert (await policy_service.get_policy(db, manager, POLICY_B)).id == POLICY_B


@pytest.mark.asyncio
async def test_owner_a_update_other_owner_policy_404(db):
    with pytest.raises(AppError):
        await policy_service.update_policy(
            db, owner_a, POLICY_B, PolicyUpdate(title="hijack")
        )


@pytest.mark.asyncio
async def test_owner_a_delete_other_owner_policy_404(db):
    with pytest.raises(AppError):
        await policy_service.delete_policy(db, owner_a, POLICY_B)


@pytest.mark.asyncio
async def test_owner_a_renew_other_owner_policy_404(db):
    with pytest.raises(AppError):
        await policy_service.renew(
            db, owner_a, POLICY_B,
            RenewPolicyRequest(expiry_date=date.today() + timedelta(days=365)),
        )


@pytest.mark.asyncio
async def test_owner_a_mark_renewed_other_owner_policy_404(db):
    with pytest.raises(AppError):
        await policy_service.mark_renewed(db, owner_a, POLICY_B)


@pytest.mark.asyncio
async def test_owner_a_installments_other_owner_policy_404(db):
    from app.services import installment_service
    with pytest.raises(AppError):
        await installment_service.list_for_policy(db, owner_a, POLICY_B)


@pytest.mark.asyncio
async def test_owner_a_documents_other_owner_policy_404(db):
    from app.services import document_service
    with pytest.raises(AppError):
        await document_service.list_documents(db, owner_a, POLICY_B)


@pytest.mark.asyncio
async def test_owner_a_alert_rule_other_owner_policy_404(db):
    with pytest.raises(AppError):
        await alert_service.get_effective_rule(db, owner_a, POLICY_B)


@pytest.mark.asyncio
async def test_owner_a_own_sub_resources_ok(db, monkeypatch):
    """Owner CAN reach their OWN policy's sub-resources (no false 404)."""
    from unittest.mock import AsyncMock

    from app.core import storage
    from app.services import document_service, installment_service
    monkeypatch.setattr(
        storage, "create_signed_download_url", AsyncMock(return_value="https://x")
    )
    assert await policy_service.get_policy(db, owner_a, POLICY_A)
    await installment_service.list_for_policy(db, owner_a, POLICY_A)
    docs = await document_service.list_documents(db, owner_a, POLICY_A)
    assert {d["file_name"] for d in docs} == {"a.pdf"}
    await alert_service.get_effective_rule(db, owner_a, POLICY_A)


# ---------------------------------------------------------------------------
# Dashboard (single + group)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_owner_a_only_own_policy(db):
    dash = await dashboard_service.get_dashboard(db, owner_a)
    assert dash["totals"]["policies"] == 1
    assert dash["totals"]["premium_inr"] == 1000  # PA only, not PA+PB
    assert {u["id"] for u in dash["upcoming"]} == {POLICY_A}


@pytest.mark.asyncio
async def test_dashboard_manager_sees_both(db):
    dash = await dashboard_service.get_dashboard(db, manager)
    assert dash["totals"]["policies"] == 2
    assert dash["totals"]["premium_inr"] == 3000  # PA + PB


@pytest.mark.asyncio
async def test_group_dashboard_owner_a_only_own(db):
    grp = await dashboard_service.get_group_dashboard(db, owner_a)
    assert grp.totals.policies == 1
    assert sum(r.policies for r in grp.by_org) == 1


@pytest.mark.asyncio
async def test_group_dashboard_manager_sees_both(db):
    grp = await dashboard_service.get_group_dashboard(db, manager)
    assert grp.totals.policies == 2
    assert sum(r.policies for r in grp.by_org) == 2


# ---------------------------------------------------------------------------
# Reports / export (data_io)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_renewal_report_owner_a_excludes_pb(db):
    rows = await data_io_service.fetch_renewal_report(db, owner_a, window_days=365)
    titles = {r.title for r in rows}
    assert titles == {"PA — A's fleet"}


@pytest.mark.asyncio
async def test_renewal_report_manager_includes_both(db):
    rows = await data_io_service.fetch_renewal_report(db, manager, window_days=365)
    assert {r.title for r in rows} == {"PA — A's fleet", "PB — B's plant"}


@pytest.mark.asyncio
async def test_policy_export_owner_a_excludes_pb(db):
    policies, _ = await data_io_service._fetch_policies_for_export(db, owner_a)
    assert {p.title for p in policies} == {"PA — A's fleet"}


@pytest.mark.asyncio
async def test_policy_export_manager_includes_both(db):
    policies, _ = await data_io_service._fetch_policies_for_export(db, manager)
    assert {p.title for p in policies} == {"PA — A's fleet", "PB — B's plant"}


# ---------------------------------------------------------------------------
# Document library
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_document_library_owner_a_excludes_pb_docs(db):
    items = await document_library_service.list_library(db, owner_a)
    assert {i.file_name for i in items} == {"a.pdf"}


@pytest.mark.asyncio
async def test_document_library_manager_sees_both_docs(db):
    items = await document_library_service.list_library(db, manager)
    assert {i.file_name for i in items} == {"a.pdf", "b.pdf"}


# ---------------------------------------------------------------------------
# Alerts feed (alert_service.list_alerts)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_alerts_owner_a_only_own_policy_alerts(db):
    alerts = await alert_service.list_alerts(db, owner_a)
    assert {a.policy_id for a in alerts} == {POLICY_A}


@pytest.mark.asyncio
async def test_list_alerts_manager_sees_both(db):
    alerts = await alert_service.list_alerts(db, manager)
    assert {a.policy_id for a in alerts} == {POLICY_A, POLICY_B}


# ---------------------------------------------------------------------------
# Notification feed + history (alerts portion owner-scoped)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notification_feed_owner_a_only_own_alerts(db):
    feed = await notification_feed_service.get_feed(db, owner_a)
    titles = [i.title for i in feed.items if i.type == "alert"]
    assert all("A's fleet" in t for t in titles)
    assert all("B's plant" not in t for t in titles)
    assert feed.unread_count == 1  # exactly PA's single alert


@pytest.mark.asyncio
async def test_notification_feed_manager_sees_both_alerts(db):
    feed = await notification_feed_service.get_feed(db, manager)
    alert_items = [i for i in feed.items if i.type == "alert"]
    assert len(alert_items) == 2


@pytest.mark.asyncio
async def test_notification_history_owner_a_only_own_alerts(db):
    hist = await notification_feed_service.get_history(db, owner_a)
    alert_titles = [i.title for i in hist.items if i.type == "alert"]
    assert len(alert_titles) == 1
    assert "A's fleet" in alert_titles[0]


# ---------------------------------------------------------------------------
# Account export (DPDP) — policies + documents owner-scoped, others not
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_account_export_owner_a_policies_and_docs_scoped(db):
    export = await account_export_service.build_export(db, owner_a)
    pol_titles = {p["title"] for p in export["policies"]["items"]}
    doc_names = {d["file_name"] for d in export["policy_documents"]["items"]}
    assert pol_titles == {"PA — A's fleet"}
    assert doc_names == {"a.pdf"}


@pytest.mark.asyncio
async def test_account_export_owner_a_team_unrestricted(db):
    """Profiles (team list) stay tenant-scoped for owners — DPDP context."""
    export = await account_export_service.build_export(db, owner_a)
    emails = {p["email"] for p in export["profiles"]["items"]}
    assert {"a@acme.test", "b@acme.test", "m@acme.test", "v@acme.test"} <= emails


@pytest.mark.asyncio
async def test_account_export_manager_sees_both_policies(db):
    export = await account_export_service.build_export(db, manager)
    pol_titles = {p["title"] for p in export["policies"]["items"]}
    assert pol_titles == {"PA — A's fleet", "PB — B's plant"}
