"""Policy document schemas (M2 — document vault + document library)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.intake import PolicyExtraction

DocType = Literal["policy", "schedule", "endorsement", "invoice", "claim", "other"]


class UploadUrlRequest(BaseModel):
    file_name: str
    content_type: str


class UploadUrlResponse(BaseModel):
    upload_url: str
    storage_path: str
    note: str = "PUT the file to upload_url, then POST the storage_path to record it."


class RecordDocumentRequest(BaseModel):
    storage_path: str
    file_name: str
    content_type: str | None = None
    size_bytes: int | None = None
    doc_type: DocType = "policy"
    content_hash: str | None = None  # hex SHA-256 of file bytes; used for dedup


class DuplicateDocumentDetail(BaseModel):
    """Returned in the error.details of a duplicate_document 409 — the existing doc."""

    id: uuid.UUID
    file_name: str
    created_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    file_name: str
    doc_type: str
    mime_type: str | None
    size_bytes: int | None
    version: int
    created_at: datetime


class DocumentWithUrl(DocumentRead):
    download_url: str


class AutoProcessResponse(BaseModel):
    """Result of auto-processing a freshly uploaded document.

    Best-effort: the document is indexed for Ask sVault (``indexed_chunks``) and,
    for text-based PDFs, sVault AI extracts policy fields (``extracted``). When an
    expiry date is found and the policy had none, it is applied so the renewal-alert
    cadence starts automatically (``expiry_applied``). Images/scanned PDFs yield
    ``indexed_chunks=0`` and a ``notes`` hint (OCR not yet supported).
    """

    indexed_chunks: int = 0
    expiry_applied: bool = False
    extracted: PolicyExtraction | None = None
    notes: str | None = None


class DocumentLibraryItem(BaseModel):
    """Cross-policy document library item with policy context and optional search snippet."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_name: str
    doc_type: str
    mime_type: str | None
    size_bytes: int | None
    created_at: datetime
    download_url: str
    policy_id: uuid.UUID
    policy_title: str
    policy_category: str
    snippet: str | None = None
