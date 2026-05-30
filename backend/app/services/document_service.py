"""Policy document service — signed-URL upload flow + metadata, scope-checked."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.errors import AppError, ErrorCode, not_found
from app.core.security import CurrentUser
from app.db.models import PolicyDocument
from app.schemas.document import RecordDocumentRequest, UploadUrlRequest
from app.services import policy_service


async def request_upload_url(
    db: AsyncSession, user: CurrentUser, policy_id: uuid.UUID, payload: UploadUrlRequest
) -> dict:
    policy = await policy_service.get_policy(db, user, policy_id)  # scope-checked (404 if not)
    if payload.content_type not in storage.ALLOWED_MIME:
        raise AppError(ErrorCode.validation_error, "Unsupported file type")
    path = storage.build_object_path(policy.tenant_id, policy.id, payload.file_name)
    upload_url = await storage.create_signed_upload_url(path)
    return {"upload_url": upload_url, "storage_path": path}


async def record_document(
    db: AsyncSession, user: CurrentUser, policy_id: uuid.UUID, payload: RecordDocumentRequest
) -> PolicyDocument:
    policy = await policy_service.get_policy(db, user, policy_id)
    if payload.content_type and payload.content_type not in storage.ALLOWED_MIME:
        raise AppError(ErrorCode.validation_error, "Unsupported file type")
    if payload.size_bytes and payload.size_bytes > storage.MAX_SIZE_BYTES:
        raise AppError(ErrorCode.validation_error, "File too large")
    # storage_path must belong to this tenant/policy (defense against forged paths).
    expected_prefix = f"{policy.tenant_id}/{policy.id}/"
    if not payload.storage_path.startswith(expected_prefix):
        raise AppError(ErrorCode.validation_error, "storage_path does not match policy")
    doc = PolicyDocument(
        tenant_id=policy.tenant_id,
        org_id=policy.org_id,
        policy_id=policy.id,
        doc_type=payload.doc_type,
        storage_path=payload.storage_path,
        file_name=payload.file_name,
        mime_type=payload.content_type,
        size_bytes=payload.size_bytes,
        uploaded_by=uuid.UUID(user.user_id),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def list_documents(
    db: AsyncSession, user: CurrentUser, policy_id: uuid.UUID
) -> list[dict]:
    await policy_service.get_policy(db, user, policy_id)  # scope-checked
    rows = (
        await db.execute(
            select(PolicyDocument)
            .where(PolicyDocument.policy_id == policy_id)
            .order_by(PolicyDocument.created_at.desc())
        )
    ).scalars().all()
    out = []
    for d in rows:
        url = await storage.create_signed_download_url(d.storage_path)
        out.append({
            "id": d.id, "file_name": d.file_name, "doc_type": d.doc_type,
            "mime_type": d.mime_type, "size_bytes": d.size_bytes, "version": d.version,
            "created_at": d.created_at, "download_url": url,
        })
    return out


async def delete_document(
    db: AsyncSession, user: CurrentUser, document_id: uuid.UUID
) -> None:
    doc = await db.get(PolicyDocument, document_id)
    if doc is None:
        raise not_found("Document not found")
    await policy_service.get_policy(db, user, doc.policy_id)  # scope-checked (404 if not)
    await storage.delete_object(doc.storage_path)
    await db.delete(doc)
    await db.commit()
