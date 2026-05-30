"""Policy document endpoints (M2 — document vault, signed-URL flow)."""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.document import (
    DocumentWithUrl,
    RecordDocumentRequest,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.services import document_service

router = APIRouter(tags=["documents"])

_read = require_permission("policy:read")
_write = require_permission("document:write")
_delete = require_permission("document:delete")


@router.post("/policies/{policy_id}/documents/upload-url", response_model=UploadUrlResponse)
async def request_upload_url(
    policy_id: uuid.UUID,
    payload: UploadUrlRequest,
    user: CurrentUser = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> UploadUrlResponse:
    result = await document_service.request_upload_url(db, user, policy_id, payload)
    return UploadUrlResponse(**result)


@router.post("/policies/{policy_id}/documents", response_model=DocumentWithUrl, status_code=201)
async def record_document(
    policy_id: uuid.UUID,
    payload: RecordDocumentRequest,
    user: CurrentUser = Depends(_write),
    db: AsyncSession = Depends(get_db),
) -> DocumentWithUrl:
    doc = await document_service.record_document(db, user, policy_id, payload)
    from app.core import storage
    url = await storage.create_signed_download_url(doc.storage_path)
    return DocumentWithUrl(
        id=doc.id, file_name=doc.file_name, doc_type=doc.doc_type, mime_type=doc.mime_type,
        size_bytes=doc.size_bytes, version=doc.version, created_at=doc.created_at,
        download_url=url,
    )


@router.get("/policies/{policy_id}/documents", response_model=list[DocumentWithUrl])
async def list_documents(
    policy_id: uuid.UUID,
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentWithUrl]:
    return await document_service.list_documents(db, user, policy_id)


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    user: CurrentUser = Depends(_delete),
    db: AsyncSession = Depends(get_db),
) -> None:
    await document_service.delete_document(db, user, document_id)
