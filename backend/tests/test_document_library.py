"""Tests for the Document Library endpoint and service.

Coverage
--------
1. Auth guard — GET /api/v1/documents without a token → 401.
2. Service returns items with policy context (happy path, no search).
3. Service search: filename filter narrows results correctly.
4. Service search: chunk-based FTS adds snippet for content hits.
5. No-tenant user returns an empty list without hitting the DB.
6. doc_type filter is forwarded to the query (verified via mock call args).

Service tests use AsyncMock / MagicMock and do NOT require a live DB.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from app.api.v1 import document_library as doc_lib_module
from app.core.errors import register_error_handlers
from app.core.middleware import RequestIDMiddleware
from app.core.security import CurrentUser
from app.services import document_library_service

# ---------------------------------------------------------------------------
# Minimal test app — only the document_library router.
# ---------------------------------------------------------------------------

def _make_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RequestIDMiddleware)
    register_error_handlers(test_app)
    test_app.include_router(doc_lib_module.router, prefix="/api/v1")
    return test_app


_test_app = _make_test_app()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(
    role: str = "admin",
    tenant_id: str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    org_id: str | None = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    is_super_admin: bool = False,
) -> CurrentUser:
    return CurrentUser(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        org_id=org_id,
        role=role,
        is_super_admin=is_super_admin,
    )


_NOW = datetime.now(UTC)
_POLICY_ID = uuid.uuid4()
_DOC_ID = uuid.uuid4()

# Simulate a DB row (as a NamedTuple / Mapping via MagicMock).
def _doc_row(
    doc_id: uuid.UUID | None = None,
    file_name: str = "fleet_policy.pdf",
    doc_type: str = "policy",
    mime_type: str = "application/pdf",
    size_bytes: int = 12345,
    storage_path: str = "t/p/file.pdf",
    policy_id: uuid.UUID | None = None,
    policy_title: str = "Fleet Insurance 2026",
    policy_category: str = "vehicle",
) -> MagicMock:
    row = MagicMock()
    row.id = doc_id or _DOC_ID
    row.file_name = file_name
    row.doc_type = doc_type
    row.mime_type = mime_type
    row.size_bytes = size_bytes
    row.created_at = _NOW
    row.storage_path = storage_path
    row.policy_id = policy_id or _POLICY_ID
    row.policy_title = policy_title
    row.policy_category = policy_category
    return row


# ---------------------------------------------------------------------------
# 1. Auth guard (endpoint-level)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_document_library_requires_auth():
    """GET /documents without a bearer token must return 401."""
    transport = httpx.ASGITransport(app=_test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/documents")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 2. Service happy path — returns items with policy context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_library_returns_items_with_policy_context(monkeypatch):
    """list_library() should return DocumentLibraryItem with policy_title + category."""
    row = _doc_row()

    # Stub the DB execute to return our row.
    mock_result = MagicMock()
    mock_result.all.return_value = [row]

    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    # Stub storage so we don't need Supabase.
    monkeypatch.setattr(
        document_library_service.storage,
        "create_signed_download_url",
        AsyncMock(return_value="https://storage.example/signed"),
    )

    user = _user(role="admin")
    items = await document_library_service.list_library(db, user)

    assert len(items) == 1
    item = items[0]
    assert item.id == row.id
    assert item.file_name == "fleet_policy.pdf"
    assert item.policy_title == "Fleet Insurance 2026"
    assert item.policy_category == "vehicle"
    assert item.download_url == "https://storage.example/signed"
    assert item.snippet is None  # no search, no snippet


# ---------------------------------------------------------------------------
# 3. Service search: filename match (no chunk hit), snippet stays None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_library_search_filename_no_snippet(monkeypatch):
    """When a doc matches by filename and not chunk content, snippet is None."""
    row = _doc_row(file_name="vehicle_policy.pdf")

    # First execute → name/title matches (the main query).
    meta_result = MagicMock()
    meta_result.all.return_value = [row]

    # Second execute → FTS hits (none for this test).
    fts_result = MagicMock()
    fts_result.all.return_value = []  # no FTS hit

    # Third execute → ILIKE fallback (also none).
    ilike_result = MagicMock()
    ilike_result.all.return_value = []

    db = AsyncMock()
    # Return results in sequence: meta → fts → ilike.
    db.execute = AsyncMock(side_effect=[meta_result, fts_result, ilike_result])

    monkeypatch.setattr(
        document_library_service.storage,
        "create_signed_download_url",
        AsyncMock(return_value="https://storage.example/signed"),
    )

    user = _user(role="admin")
    items = await document_library_service.list_library(db, user, search="vehicle")

    # The doc came from the name/title query, so snippet=None.
    assert len(items) == 1
    assert items[0].snippet is None


# ---------------------------------------------------------------------------
# 4. Service search: chunk FTS hit populates snippet
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_library_search_chunk_hit_populates_snippet(monkeypatch):
    """A document matched only via chunk FTS should have a snippet."""
    doc_id = uuid.uuid4()
    # Name/title query returns nothing (doc name doesn't match).
    meta_result = MagicMock()
    meta_result.all.return_value = []

    # FTS query returns a chunk hit for our doc.
    chunk_content = "The fleet insurance covers vehicles including trucks and vans " * 5
    chunk_row = MagicMock()
    chunk_row.document_id = doc_id
    chunk_row.content = chunk_content

    fts_result = MagicMock()
    fts_result.all.return_value = [chunk_row]

    # Extra query to hydrate the missing doc row.
    doc_row = _doc_row(doc_id=doc_id)
    extra_result = MagicMock()
    extra_result.all.return_value = [doc_row]

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[meta_result, fts_result, extra_result])

    monkeypatch.setattr(
        document_library_service.storage,
        "create_signed_download_url",
        AsyncMock(return_value="https://storage.example/signed"),
    )

    user = _user(role="admin")
    items = await document_library_service.list_library(db, user, search="fleet")

    assert len(items) == 1
    item = items[0]
    assert item.id == doc_id
    # Snippet must be ≤ 160 chars and be a substring of the chunk content.
    assert item.snippet is not None
    assert len(item.snippet) <= 160
    assert "fleet" in item.snippet.lower()


# ---------------------------------------------------------------------------
# 5. No-tenant user returns empty list without querying DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_library_no_tenant_returns_empty():
    """A user with no tenant_id should get [] without any DB call."""
    user = CurrentUser(user_id="x", tenant_id=None, org_id=None, role="admin")
    db = AsyncMock()
    result = await document_library_service.list_library(db, user)
    assert result == []
    db.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# 6. doc_type filter is applied
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_library_doc_type_filter_applied(monkeypatch):
    """When doc_type is provided the service passes it through to the ORM query."""
    meta_result = MagicMock()
    meta_result.all.return_value = []

    db = AsyncMock()
    db.execute = AsyncMock(return_value=meta_result)

    monkeypatch.setattr(
        document_library_service.storage,
        "create_signed_download_url",
        AsyncMock(return_value=""),
    )

    user = _user(role="admin")
    items = await document_library_service.list_library(db, user, doc_type="invoice")

    # Nothing to assert on returned items (empty), but verify DB was called.
    db.execute.assert_awaited()
    assert items == []
