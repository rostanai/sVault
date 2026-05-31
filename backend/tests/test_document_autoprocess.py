"""Tests for document_service.auto_process_document (post-upload auto-processing).

Coverage
--------
1. Text PDF with an expiry date → indexes for RAG, extracts fields, and auto-fills
   the policy's missing expiry date (so renewal alerts schedule themselves).
2. Existing policy expiry is NEVER overwritten.
3. sVault AI unconfigured (AppError) → soft note, no crash, indexing still happens.
4. Indexing failure is swallowed and never breaks extraction.
5. Document not belonging to the policy → 404.

All tests use AsyncMock/MagicMock — no live DB, storage, or LLM provider.
"""
from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import AppError, ErrorCode
from app.core.security import CurrentUser
from app.services import document_service

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
POLICY_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
DOC_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


def _user(role: str = "admin") -> CurrentUser:
    return CurrentUser(
        user_id=str(uuid.uuid4()),
        tenant_id=TENANT,
        org_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        role=role,
        is_super_admin=False,
    )


def _policy(expiry: date | None = None) -> MagicMock:
    p = MagicMock()
    p.id = POLICY_ID
    p.tenant_id = uuid.UUID(TENANT)
    p.expiry_date = expiry
    return p


def _doc() -> MagicMock:
    d = MagicMock()
    d.id = DOC_ID
    d.policy_id = POLICY_ID
    d.storage_path = f"{TENANT}/{POLICY_ID}/policy.pdf"
    d.mime_type = "application/pdf"
    return d


def _db(doc: MagicMock | None) -> MagicMock:
    db = MagicMock()
    db.get = AsyncMock(return_value=doc)
    db.commit = AsyncMock()
    return db


def _httpx_returning(content: bytes = b"%PDF-1.4 fake"):
    """Build a patchable httpx.AsyncClient whose .get() returns `content`."""
    resp = MagicMock()
    resp.content = content
    resp.raise_for_status = MagicMock()
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=cm)
    return factory


def _extraction(expiry: str | None = "2026-08-01", notes: str | None = None) -> dict:
    return {
        "category": "factory_property", "title": "Fire Cover", "policy_number": "X1",
        "insurer_name": "ACME", "sum_insured_inr": "5000000", "premium_inr": "50000",
        "gst_inr": "9000", "inception_date": "2025-08-01", "expiry_date": expiry,
        "extracted_text_chars": 1200, "notes": notes,
    }


@pytest.mark.asyncio
async def test_auto_process_indexes_extracts_and_applies_expiry():
    policy = _policy(expiry=None)
    db = _db(_doc())
    with patch("app.services.policy_service.get_policy", new=AsyncMock(return_value=policy)), \
         patch("app.services.rag_service.index_bytes", new=AsyncMock(return_value=7)), \
         patch("app.services.document_service.storage.create_signed_download_url",
               new=AsyncMock(return_value="https://signed")), \
         patch("app.services.document_service.httpx.AsyncClient", _httpx_returning()), \
         patch("app.services.extraction_service.extract_policy_fields",
               new=AsyncMock(return_value=_extraction(expiry="2026-08-01"))):
        out = await document_service.auto_process_document(
            db, _user(), POLICY_ID, DOC_ID, ai_key="sk-test"
        )

    assert out["indexed_chunks"] == 7
    assert out["expiry_applied"] is True
    assert policy.expiry_date == date(2026, 8, 1)
    assert out["extracted"]["expiry_date"] == "2026-08-01"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_auto_process_never_overwrites_existing_expiry():
    policy = _policy(expiry=date(2026, 1, 1))
    db = _db(_doc())
    with patch("app.services.policy_service.get_policy", new=AsyncMock(return_value=policy)), \
         patch("app.services.rag_service.index_bytes", new=AsyncMock(return_value=3)), \
         patch("app.services.document_service.storage.create_signed_download_url",
               new=AsyncMock(return_value="https://signed")), \
         patch("app.services.document_service.httpx.AsyncClient", _httpx_returning()), \
         patch("app.services.extraction_service.extract_policy_fields",
               new=AsyncMock(return_value=_extraction(expiry="2026-08-01"))):
        out = await document_service.auto_process_document(
            db, _user(), POLICY_ID, DOC_ID, ai_key="sk-test"
        )

    assert out["expiry_applied"] is False
    assert policy.expiry_date == date(2026, 1, 1)  # untouched


@pytest.mark.asyncio
async def test_auto_process_ai_unconfigured_is_soft_note():
    policy = _policy(expiry=None)
    db = _db(_doc())
    err = AppError(ErrorCode.internal_error, "sVault AI is not configured")
    with patch("app.services.policy_service.get_policy", new=AsyncMock(return_value=policy)), \
         patch("app.services.rag_service.index_bytes", new=AsyncMock(return_value=2)), \
         patch("app.services.document_service.storage.create_signed_download_url",
               new=AsyncMock(return_value="https://signed")), \
         patch("app.services.document_service.httpx.AsyncClient", _httpx_returning()), \
         patch("app.services.extraction_service.extract_policy_fields",
               new=AsyncMock(side_effect=err)):
        out = await document_service.auto_process_document(
            db, _user(), POLICY_ID, DOC_ID, ai_key=None
        )

    assert out["indexed_chunks"] == 2          # indexing still happened
    assert out["expiry_applied"] is False
    assert "not configured" in (out["notes"] or "")


@pytest.mark.asyncio
async def test_auto_process_index_failure_does_not_break_extraction():
    policy = _policy(expiry=None)
    db = _db(_doc())
    with patch("app.services.policy_service.get_policy", new=AsyncMock(return_value=policy)), \
         patch("app.services.rag_service.index_bytes",
               new=AsyncMock(side_effect=RuntimeError("boom"))), \
         patch("app.services.document_service.storage.create_signed_download_url",
               new=AsyncMock(return_value="https://signed")), \
         patch("app.services.document_service.httpx.AsyncClient", _httpx_returning()), \
         patch("app.services.extraction_service.extract_policy_fields",
               new=AsyncMock(return_value=_extraction(expiry="2026-08-01"))):
        out = await document_service.auto_process_document(
            db, _user(), POLICY_ID, DOC_ID, ai_key="sk-test"
        )

    assert out["indexed_chunks"] == 0          # index failed, swallowed
    assert out["expiry_applied"] is True       # extraction still succeeded


@pytest.mark.asyncio
async def test_auto_process_rejects_doc_from_other_policy():
    policy = _policy()
    doc = _doc()
    doc.policy_id = uuid.uuid4()  # belongs to a different policy
    db = _db(doc)
    with patch("app.services.policy_service.get_policy", new=AsyncMock(return_value=policy)):
        with pytest.raises(AppError) as ei:
            await document_service.auto_process_document(
                db, _user(), POLICY_ID, DOC_ID, ai_key="sk-test"
            )
    assert ei.value.code == ErrorCode.not_found
