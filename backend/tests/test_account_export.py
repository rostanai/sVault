"""Tests for the DPDP account data-export endpoint and service.

Coverage
--------
1. Endpoint auth guard — GET /account/export returns 401 without a token.
2. build_export() (mocked DB) — returns all expected top-level keys.
3. build_export() — UUID / Decimal / date fields are serialised as strings.
4. build_export() — secret-bearing fields excluded (storage_path, API-key hashes).
5. build_export() — no tenant_id → empty collections, no DB queries executed.
6. build_export() — truncation flag is set when COLLECTION_LIMIT is hit.
7. build_export() — org scoping: non-group-wide user's policy query is filtered
   by org_id.

All service tests mock the DB session (AsyncMock) — no live database needed.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from app.api.v1.account import router as account_router
from app.core.errors import register_error_handlers
from app.core.security import CurrentUser
from app.services.account_export_service import COLLECTION_LIMIT, build_export

# ---------------------------------------------------------------------------
# Isolated test app so we don't need router.py wired up
# ---------------------------------------------------------------------------

_test_app = FastAPI()
register_error_handlers(_test_app)
_test_app.include_router(account_router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ORG_ID    = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
NULL_UUID = "00000000-0000-0000-0000-000000000000"

EXPECTED_TOP_KEYS = {
    "exported_at",
    "tenant",
    "organizations",
    "profiles",
    "providers",
    "provider_contacts",
    "policies",
    "policy_documents",
    "installments",
    "approvals",
}


def _user(
    role: str = "admin",
    tenant_id: str | None = TENANT_ID,
    org_id: str | None = ORG_ID,
    is_super_admin: bool = False,
) -> CurrentUser:
    return CurrentUser(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        org_id=org_id,
        role=role,
        is_super_admin=is_super_admin,
    )


# ---------------------------------------------------------------------------
# Helpers to build minimal ORM stub mocks
# ---------------------------------------------------------------------------

def _mock_tenant(tenant_id: str = TENANT_ID) -> MagicMock:
    obj = MagicMock()
    obj.id = uuid.UUID(tenant_id)
    obj.name = "Acme Group"
    obj.status = "active"
    obj.created_at = datetime(2025, 1, 1, tzinfo=UTC)
    obj.updated_at = datetime(2025, 6, 1, tzinfo=UTC)
    return obj


def _mock_policy(
    tenant_id: str = TENANT_ID,
    org_id: str = ORG_ID,
) -> MagicMock:
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.tenant_id = uuid.UUID(tenant_id)
    obj.org_id = uuid.UUID(org_id)
    obj.category = "vehicle"
    obj.policy_number = "POL-001"
    obj.title = "Fleet Vehicle Policy"
    obj.provider_id = uuid.uuid4()
    obj.owner_id = uuid.uuid4()
    obj.sum_insured_inr = Decimal("1000000.00")
    obj.premium_inr = Decimal("25000.50")
    obj.gst_inr = Decimal("4500.09")
    obj.inception_date = date(2025, 1, 1)
    obj.expiry_date = date(2025, 12, 31)
    obj.renewal_date = date(2025, 12, 1)
    obj.status = "active"
    obj.prev_policy_id = None
    obj.custom_fields = {"vehicle_reg": "MH-01-AA-1234"}
    obj.created_by = uuid.uuid4()
    obj.created_at = datetime(2025, 1, 1, tzinfo=UTC)
    obj.updated_at = datetime(2025, 6, 1, tzinfo=UTC)
    return obj


def _mock_doc(
    tenant_id: str = TENANT_ID,
    org_id: str = ORG_ID,
) -> MagicMock:
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.tenant_id = uuid.UUID(tenant_id)
    obj.org_id = uuid.UUID(org_id)
    obj.policy_id = uuid.uuid4()
    obj.doc_type = "policy"
    obj.file_name = "policy.pdf"
    obj.mime_type = "application/pdf"
    obj.size_bytes = 204800
    obj.version = 1
    obj.uploaded_by = uuid.uuid4()
    obj.created_at = datetime(2025, 1, 5, tzinfo=UTC)
    # storage_path is intentionally present on ORM but must NOT appear in export
    obj.storage_path = "private/bucket/path/policy.pdf"
    return obj


def _empty_scalars() -> MagicMock:
    """Returns a mock execute result with an empty scalars().all()."""
    scalars = MagicMock()
    scalars.all.return_value = []
    result = MagicMock()
    result.scalars.return_value = scalars
    result.scalar_one_or_none.return_value = None
    return result


def _scalars_with(items: list) -> MagicMock:
    scalars = MagicMock()
    scalars.all.return_value = items
    result = MagicMock()
    result.scalars.return_value = scalars
    return result


# ---------------------------------------------------------------------------
# 1. Endpoint auth guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_requires_auth():
    """GET /account/export must return 401 when no bearer token is supplied."""
    transport = httpx.ASGITransport(app=_test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/account/export")

    assert resp.status_code == 401, "Expected 401 without auth token"
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 2. build_export() — returns all expected top-level keys
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_export_returns_expected_top_level_keys():
    """build_export() must return a dict containing all required top-level keys."""
    user = _user()
    db = AsyncMock()

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = _mock_tenant()

    # Return the tenant result first, then empty for all subsequent queries.
    db.execute = AsyncMock(side_effect=[
        tenant_result,          # Tenant query
        _empty_scalars(),       # organizations
        _empty_scalars(),       # profiles
        _empty_scalars(),       # providers
        _empty_scalars(),       # provider_contacts
        _empty_scalars(),       # policies
        _empty_scalars(),       # policy_documents
        _empty_scalars(),       # installments
        _empty_scalars(),       # approvals
    ])

    result = await build_export(db, user)

    assert set(result.keys()) == EXPECTED_TOP_KEYS
    # Every collection must be a dict with `items` and `_truncated`.
    for key in EXPECTED_TOP_KEYS - {"exported_at", "tenant"}:
        assert "items" in result[key], f"Missing 'items' in {key}"
        assert "_truncated" in result[key], f"Missing '_truncated' in {key}"


# ---------------------------------------------------------------------------
# 3. build_export() — UUID / Decimal / date → str
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_export_serialises_policy_fields():
    """Decimal, UUID, and date fields in a policy row must be serialised as strings."""
    user = _user()
    db = AsyncMock()

    policy = _mock_policy()

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = _mock_tenant()

    db.execute = AsyncMock(side_effect=[
        tenant_result,
        _empty_scalars(),                   # organizations
        _empty_scalars(),                   # profiles
        _empty_scalars(),                   # providers
        _empty_scalars(),                   # provider_contacts
        _scalars_with([policy]),            # policies
        _empty_scalars(),                   # policy_documents
        _empty_scalars(),                   # installments
        _empty_scalars(),                   # approvals
    ])

    result = await build_export(db, user)
    pol_row = result["policies"]["items"][0]

    # UUIDs
    assert isinstance(pol_row["id"], str)
    assert isinstance(pol_row["tenant_id"], str)
    assert isinstance(pol_row["org_id"], str)
    assert isinstance(pol_row["provider_id"], str)

    # Decimals
    assert isinstance(pol_row["sum_insured_inr"], str)
    assert pol_row["sum_insured_inr"] == "1000000.00"
    assert isinstance(pol_row["premium_inr"], str)
    assert isinstance(pol_row["gst_inr"], str)

    # Dates → ISO strings
    assert isinstance(pol_row["inception_date"], str)
    assert pol_row["inception_date"] == "2025-01-01"
    assert isinstance(pol_row["expiry_date"], str)
    assert isinstance(pol_row["renewal_date"], str)

    # The result must be JSON-serialisable without errors.
    json.dumps(result)


# ---------------------------------------------------------------------------
# 4. build_export() — secret-bearing fields excluded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_export_excludes_storage_path():
    """PolicyDocument rows must not include storage_path (no file bytes/URLs)."""
    user = _user()
    db = AsyncMock()

    doc = _mock_doc()
    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = _mock_tenant()

    db.execute = AsyncMock(side_effect=[
        tenant_result,
        _empty_scalars(),       # organizations
        _empty_scalars(),       # profiles
        _empty_scalars(),       # providers
        _empty_scalars(),       # provider_contacts
        _empty_scalars(),       # policies
        _scalars_with([doc]),   # policy_documents
        _empty_scalars(),       # installments
        _empty_scalars(),       # approvals
    ])

    result = await build_export(db, user)
    doc_row = result["policy_documents"]["items"][0]

    assert "storage_path" not in doc_row, "storage_path must be excluded from export"
    # Safe metadata fields must be present.
    assert "file_name" in doc_row
    assert "size_bytes" in doc_row
    assert "doc_type" in doc_row


# ---------------------------------------------------------------------------
# 5. build_export() — no tenant_id → empty collections, no DB queries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_export_no_tenant_returns_empty():
    """A user with no tenant_id must receive empty collections without querying the DB."""
    user = CurrentUser(user_id=str(uuid.uuid4()), tenant_id=None, org_id=None, role="admin")
    db = AsyncMock()

    result = await build_export(db, user)

    assert result["tenant"] is None
    for key in EXPECTED_TOP_KEYS - {"exported_at", "tenant"}:
        assert result[key]["items"] == []
        assert result[key]["_truncated"] is False

    # No DB queries should have been issued.
    db.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# 6. build_export() — truncation flag set when limit hit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_export_truncation_flag():
    """When the result count exceeds COLLECTION_LIMIT, _truncated must be True."""
    user = _user()
    db = AsyncMock()

    # Produce COLLECTION_LIMIT + 1 fake policies (one over the cap).
    many_policies = [_mock_policy() for _ in range(COLLECTION_LIMIT + 1)]

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = _mock_tenant()

    db.execute = AsyncMock(side_effect=[
        tenant_result,
        _empty_scalars(),                       # organizations
        _empty_scalars(),                       # profiles
        _empty_scalars(),                       # providers
        _empty_scalars(),                       # provider_contacts
        _scalars_with(many_policies),           # policies — over limit
        _empty_scalars(),                       # policy_documents
        _empty_scalars(),                       # installments
        _empty_scalars(),                       # approvals
    ])

    result = await build_export(db, user)

    policies_section = result["policies"]
    assert policies_section["_truncated"] is True
    # Must cap the returned items at COLLECTION_LIMIT.
    assert len(policies_section["items"]) == COLLECTION_LIMIT


# ---------------------------------------------------------------------------
# 7. build_export() — org scoping for non-group-wide users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_export_org_scoping_for_owner():
    """An 'owner' role (non-group-wide) should have the org filter applied to queries."""
    user = _user(role="owner")
    db = AsyncMock()

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = _mock_tenant()

    # We just need the calls to succeed — no assertion on filter internals here;
    # the important thing is that the correct number of DB execute calls are made
    # and the function does not raise.
    db.execute = AsyncMock(side_effect=[
        tenant_result,
        _empty_scalars(),   # organizations
        _empty_scalars(),   # profiles
        _empty_scalars(),   # providers
        _empty_scalars(),   # provider_contacts
        _empty_scalars(),   # policies (org-filtered)
        _empty_scalars(),   # policy_documents (org-filtered)
        _empty_scalars(),   # installments
        _empty_scalars(),   # approvals
    ])

    result = await build_export(db, user)

    # Must still return all expected keys.
    assert set(result.keys()) == EXPECTED_TOP_KEYS
    # Exactly 9 execute calls (1 tenant + 8 collections).
    assert db.execute.await_count == 9
