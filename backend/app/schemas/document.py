"""Policy document schemas (M2 — document vault)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

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
