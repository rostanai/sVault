"""Tests for the Policy Auto-Intake (AI extraction) endpoint and service.

Coverage
--------
1. Auth guard — POST /api/v1/policies/extract without a token → 401.
   Uses a minimal test app that includes the intake router (the main app's
   router.py is not modified by this engineer — the tech-lead adds the include).
2. Scanned/empty-text path — returns nulls + extracted_text_chars=0 + note, no AI call.
3. JSON mapping — monkeypatched AI call returns a known JSON string; asserts fields map
   correctly and an invalid category value is coerced to null.
4. Parse failure — AI returns malformed JSON → nulls + parse-failure note.
5. Unconfigured AI — svault_ai_api_key empty → AppError internal_error.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from app.api.v1 import intake as intake_module
from app.core.errors import register_error_handlers
from app.core.middleware import RequestIDMiddleware
from app.services import extraction_service

# ---------------------------------------------------------------------------
# Minimal test app — only the intake router, same error handling as prod app.
# Used for endpoint-level tests. The main app's router.py is left untouched;
# the tech-lead will add the include line when integrating.
# ---------------------------------------------------------------------------

def _make_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RequestIDMiddleware)
    register_error_handlers(test_app)
    test_app.include_router(intake_module.router, prefix="/api/v1")
    return test_app


_test_app = _make_test_app()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_pdf_bytes() -> bytes:
    """Return a minimal but structurally valid PDF with zero page text content.

    pypdf will successfully open it and extract an empty string — simulating a
    scanned document without raising an exception.
    """
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n190\n%%EOF"
    )
    return pdf


def _make_openai_mock(json_payload: dict | str) -> MagicMock:
    """Return a mock AsyncOpenAI instance whose chat.completions.create returns json_payload."""
    content = json.dumps(json_payload) if isinstance(json_payload, dict) else json_payload

    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_create = AsyncMock(return_value=mock_response)
    mock_completions = MagicMock()
    mock_completions.create = mock_create
    mock_chat = MagicMock()
    mock_chat.completions = mock_completions
    mock_client = MagicMock()
    mock_client.chat = mock_chat
    return mock_client


# ---------------------------------------------------------------------------
# 1. Auth guard (endpoint-level)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_endpoint_requires_auth():
    """No Bearer token → 401 with error code 'unauthorized'."""
    transport = httpx.ASGITransport(app=_test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/policies/extract",
            files={"file": ("policy.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# 2. Scanned / empty-text path (service-level)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scanned_pdf_returns_nulls_no_ai_call(monkeypatch):
    """When pypdf yields no text, sVault AI must NOT be called.

    Result must have all domain fields null, extracted_text_chars=0,
    and the scanned-document note.
    """
    monkeypatch.setattr(extraction_service, "_extract_text", lambda raw, mime: "")

    # Patch AsyncOpenAI at module level; if it is constructed the test would fail
    # because there is no API key. Verify it's never reached.
    ai_was_called = False

    class _FakeOpenAI:
        def __init__(self, *a, **kw):
            nonlocal ai_was_called
            ai_was_called = True

    monkeypatch.setattr(extraction_service, "AsyncOpenAI", _FakeOpenAI)

    result = await extraction_service.extract_policy_fields(b"fake-bytes", "application/pdf")

    assert not ai_was_called, "sVault AI must not be called for scanned documents"
    assert result["extracted_text_chars"] == 0
    assert result["category"] is None
    assert result["title"] is None
    assert result["policy_number"] is None
    assert result["insurer_name"] is None
    assert result["sum_insured_inr"] is None
    assert result["premium_inr"] is None
    assert result["gst_inr"] is None
    assert result["inception_date"] is None
    assert result["expiry_date"] is None
    assert result["notes"] is not None
    assert "scanned" in result["notes"].lower()


@pytest.mark.asyncio
async def test_minimal_empty_pdf_is_treated_as_scanned():
    """A valid PDF with no text content is treated as a scanned document."""
    result = await extraction_service.extract_policy_fields(
        _minimal_pdf_bytes(), "application/pdf"
    )
    assert result["extracted_text_chars"] == 0
    assert result["notes"] is not None
    assert "scanned" in result["notes"].lower()


# ---------------------------------------------------------------------------
# 3. JSON mapping — valid AI response (service-level)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_ai_response_maps_all_fields(monkeypatch):
    """A well-formed AI JSON response maps correctly to the extraction schema."""
    sample_text = "This is a Vehicle Insurance Policy. Policy No: VH-2024-001. " * 40

    monkeypatch.setattr(extraction_service, "_extract_text", lambda raw, mime: sample_text)
    monkeypatch.setattr(extraction_service.settings, "svault_ai_api_key", "test-key")

    ai_payload = {
        "category": "vehicle",
        "title": "Fleet Motor Insurance",
        "policy_number": "VH-2024-001",
        "insurer_name": "New India Assurance",
        "sum_insured_inr": "10000000",
        "premium_inr": "250000",
        "gst_inr": "45000",
        "inception_date": "2024-04-01",
        "expiry_date": "2025-03-31",
    }
    mock_client = _make_openai_mock(ai_payload)
    monkeypatch.setattr(extraction_service, "AsyncOpenAI", lambda **kw: mock_client)

    result = await extraction_service.extract_policy_fields(b"fake-pdf-bytes", "application/pdf")

    assert result["category"] == "vehicle"
    assert result["title"] == "Fleet Motor Insurance"
    assert result["policy_number"] == "VH-2024-001"
    assert result["insurer_name"] == "New India Assurance"
    assert result["sum_insured_inr"] == "10000000"
    assert result["premium_inr"] == "250000"
    assert result["gst_inr"] == "45000"
    assert result["inception_date"] == "2024-04-01"
    assert result["expiry_date"] == "2025-03-31"
    assert result["extracted_text_chars"] == len(sample_text)
    assert result["notes"] is None


@pytest.mark.asyncio
async def test_invalid_category_coerced_to_null(monkeypatch):
    """If the AI returns a category not in the allowed enum, it must become null."""
    sample_text = "Policy document content. " * 50
    monkeypatch.setattr(extraction_service, "_extract_text", lambda raw, mime: sample_text)
    monkeypatch.setattr(extraction_service.settings, "svault_ai_api_key", "test-key")

    ai_payload = {
        "category": "marine_cargo",  # not in the allowed set
        "title": "Marine Cargo Policy",
        "policy_number": "MC-001",
        "insurer_name": "Oriental Insurance",
        "sum_insured_inr": None,
        "premium_inr": None,
        "gst_inr": None,
        "inception_date": None,
        "expiry_date": None,
    }
    mock_client = _make_openai_mock(ai_payload)
    monkeypatch.setattr(extraction_service, "AsyncOpenAI", lambda **kw: mock_client)

    result = await extraction_service.extract_policy_fields(b"fake-pdf-bytes", "application/pdf")

    assert result["category"] is None, "Unknown category must be coerced to null"
    assert result["title"] == "Marine Cargo Policy"


# ---------------------------------------------------------------------------
# 4. Parse failure path (service-level)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_malformed_ai_json_returns_nulls_with_note(monkeypatch):
    """If sVault AI returns non-JSON, all domain fields are null and a note is set."""
    sample_text = "Policy document. " * 50
    monkeypatch.setattr(extraction_service, "_extract_text", lambda raw, mime: sample_text)
    monkeypatch.setattr(extraction_service.settings, "svault_ai_api_key", "test-key")

    mock_client = _make_openai_mock("This is not valid JSON {{ broken }}")
    monkeypatch.setattr(extraction_service, "AsyncOpenAI", lambda **kw: mock_client)

    result = await extraction_service.extract_policy_fields(b"fake-pdf-bytes", "application/pdf")

    assert result["category"] is None
    assert result["title"] is None
    assert result["extracted_text_chars"] == len(sample_text)
    assert result["notes"] is not None
    assert "parse" in result["notes"].lower()


# ---------------------------------------------------------------------------
# 5. Unconfigured sVault AI (service-level)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_raises_when_ai_not_configured(monkeypatch):
    """Empty svault_ai_api_key → AppError with code internal_error."""
    sample_text = "Some policy text. " * 30
    monkeypatch.setattr(extraction_service, "_extract_text", lambda raw, mime: sample_text)
    monkeypatch.setattr(extraction_service.settings, "svault_ai_api_key", "")

    from app.core.errors import AppError, ErrorCode

    with pytest.raises(AppError) as exc_info:
        await extraction_service.extract_policy_fields(b"fake-bytes", "application/pdf")

    assert exc_info.value.code == ErrorCode.internal_error
    assert "not configured" in exc_info.value.message.lower()
