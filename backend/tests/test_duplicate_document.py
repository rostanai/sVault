"""Duplicate-document detection — unit-level checks (no DB needed).

The full upload→dedup path is exercised end-to-end by the document integration
tests; here we lock in the error contract and schema so the frontend can rely on
the typed 409 + details shape.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime


def test_duplicate_document_error_code_maps_to_409():
    from app.core.errors import AppError, ErrorCode

    err = AppError(
        ErrorCode.duplicate_document,
        "This document has already been uploaded to this policy.",
    )
    assert err.http_status == 409
    assert err.code == "duplicate_document"


def test_record_document_request_content_hash_optional():
    from app.schemas.document import RecordDocumentRequest

    req = RecordDocumentRequest(
        storage_path="t/p/x.pdf",
        file_name="x.pdf",
        content_type="application/pdf",
        size_bytes=100,
    )
    assert req.content_hash is None

    req2 = RecordDocumentRequest(
        storage_path="t/p/x.pdf",
        file_name="x.pdf",
        content_hash="a" * 64,
    )
    assert req2.content_hash == "a" * 64


def test_duplicate_document_detail_serialises():
    from app.schemas.document import DuplicateDocumentDetail

    detail = DuplicateDocumentDetail(
        id=uuid.uuid4(),
        file_name="policy.pdf",
        created_at=datetime.now(tz=UTC),
    )
    dumped = detail.model_dump(mode="json")
    assert set(dumped) == {"id", "file_name", "created_at"}
