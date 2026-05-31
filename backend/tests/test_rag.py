"""AI "Ask sVault" (RAG) tests.

Coverage
--------
1. chunk_text() — windowing/overlap behaviour and empty-input handling.
2. _accessible_orgs() — tenant-wide vs org-scoped vs no-access resolution.
3. ask() — raises when sVault AI is not configured (no provider key).
4. Endpoint auth guards — /ask and the ingest route reject anonymous requests.

Service tests use AsyncMock / MagicMock and do NOT require a live DB or the
LLM provider.  The provider is branded "sVault AI" everywhere — these tests
also assert the system prompt never leaks the underlying vendor name.
"""
from __future__ import annotations

import uuid

import httpx
import pytest

from app.core.errors import AppError, ErrorCode
from app.core.security import CurrentUser
from app.main import app
from app.services import rag_service

NULL_UUID = "00000000-0000-0000-0000-000000000000"


def _user(
    role: str = "admin",
    org_id: str | None = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    is_super_admin: bool = False,
) -> CurrentUser:
    return CurrentUser(
        user_id=str(uuid.uuid4()),
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        org_id=org_id,
        role=role,
        is_super_admin=is_super_admin,
    )


# ---------------------------------------------------------------------------
# 1. chunk_text
# ---------------------------------------------------------------------------

def test_chunk_text_empty_returns_no_chunks():
    assert rag_service.chunk_text("") == []
    assert rag_service.chunk_text("   ") == []


def test_chunk_text_short_text_single_chunk():
    chunks = rag_service.chunk_text("hello world", size=800, overlap=100)
    assert chunks == ["hello world"]


def test_chunk_text_windows_with_overlap():
    words = " ".join(f"w{i}" for i in range(250))
    chunks = rag_service.chunk_text(words, size=100, overlap=20)
    # step = size - overlap = 80 → starts at 0, 80, 160, 240 → 4 chunks
    assert len(chunks) == 4
    assert all(len(c.split()) <= 100 for c in chunks)
    # Overlap: the 2nd window starts 80 words in, repeating w80..w99 from window 1.
    assert "w80" in chunks[0].split()
    assert "w80" in chunks[1].split()


def test_chunk_text_terminates_when_overlap_ge_size():
    # Guard against an infinite loop when overlap >= size (step floored to 1).
    chunks = rag_service.chunk_text("a b c", size=2, overlap=5)
    assert len(chunks) >= 1


# ---------------------------------------------------------------------------
# 2. _accessible_orgs
# ---------------------------------------------------------------------------

def test_accessible_orgs_super_admin_is_tenant_wide():
    assert rag_service._accessible_orgs(_user(is_super_admin=True)) is None


def test_accessible_orgs_scoped_user_returns_org_uuid():
    org = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    result = rag_service._accessible_orgs(_user(role="viewer", org_id=org))
    assert isinstance(result, uuid.UUID)
    assert str(result) == org


def test_accessible_orgs_no_org_means_no_access():
    assert rag_service._accessible_orgs(_user(role="viewer", org_id=None)) == "NONE"


# ---------------------------------------------------------------------------
# 3. ask() guards
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ask_raises_when_not_configured(monkeypatch):
    monkeypatch.setattr(rag_service.settings, "svault_ai_api_key", "")
    with pytest.raises(AppError) as exc:
        await rag_service.ask(db=None, user=_user(), question="What is my cover?")
    assert "not configured" in str(exc.value.message).lower()


def test_system_prompt_brands_svault_ai_only():
    prompt = rag_service.SYSTEM_PROMPT.lower()
    assert "svault ai" in prompt
    # Never surface the underlying provider's name to users.
    assert "deepseek" not in prompt
    assert "openai" not in prompt


# ---------------------------------------------------------------------------
# 4. Endpoint auth guards
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("path", [
    "/api/v1/ask",
    f"/api/v1/policies/{NULL_UUID}/documents/{NULL_UUID}/ingest",
])
async def test_ai_endpoints_require_auth(path):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(path, json={"question": "what is my fleet cover?"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 5. ingest_document enforces object-level policy scope (BOLA fix)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_document_404_when_missing():
    """ingest_document must 404 when the document row does not exist."""
    from unittest.mock import AsyncMock

    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    with pytest.raises(AppError) as ei:
        await rag_service.ingest_document(db, _user(), uuid.uuid4())
    assert ei.value.code.value == "not_found"


@pytest.mark.asyncio
async def test_ingest_document_enforces_policy_scope():
    """A document whose policy is not accessible to the caller must 404 — closes the
    BOLA where a same-tenant user passed an accessible policy_id + a foreign doc_id."""
    from unittest.mock import AsyncMock, MagicMock, patch

    doc = MagicMock()
    doc.policy_id = uuid.uuid4()
    db = AsyncMock()
    db.get = AsyncMock(return_value=doc)
    # policy_service.get_policy is the scope gate; simulate "not yours" → 404.
    with patch(
        "app.services.policy_service.get_policy",
        new=AsyncMock(side_effect=AppError(ErrorCode.not_found, "Policy not found")),
    ):
        with pytest.raises(AppError) as ei:
            await rag_service.ingest_document(db, _user(), uuid.uuid4())
    assert ei.value.code.value == "not_found"
