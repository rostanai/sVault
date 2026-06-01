"""Policy document service — signed-URL upload flow + metadata, scope-checked."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.errors import AppError, ErrorCode, not_found
from app.core.security import CurrentUser
from app.db.models import PolicyDocument
from app.schemas.document import RecordDocumentRequest, UploadUrlRequest
from app.services import policy_service

log = logging.getLogger("svault.documents")


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
    # Sign all download URLs concurrently (one storage round-trip each) rather than
    # serially — N sequential calls collapse into one parallel batch.
    # return_exceptions=True so a single un-signable object (missing file in the
    # bucket, transient storage error) yields an empty URL instead of 502-ing the
    # whole list. Mirrors document_library_service.
    urls = await asyncio.gather(
        *(storage.create_signed_download_url(d.storage_path) for d in rows),
        return_exceptions=True,
    )
    return [
        {
            "id": d.id, "file_name": d.file_name, "doc_type": d.doc_type,
            "mime_type": d.mime_type, "size_bytes": d.size_bytes, "version": d.version,
            "created_at": d.created_at,
            "download_url": "" if isinstance(url, BaseException) else url,
        }
        for d, url in zip(rows, urls, strict=True)
    ]


async def auto_process_document(
    db: AsyncSession,
    user: CurrentUser,
    policy_id: uuid.UUID,
    document_id: uuid.UUID,
    *,
    ai_key: str | None,
) -> dict:
    """Best-effort post-upload processing of a document.

    1. Index the document for "Ask sVault" (text PDFs → searchable chunks).
    2. AI-extract structured policy fields (text PDFs only).
    3. If an expiry date is found and the policy had none, apply it so the
       renewal-alert cadence (60/30/15/7/1d) starts automatically.

    Never raises on AI/index/network failure — those degrade gracefully into the
    response ``notes`` so a flaky AI call can never break the upload flow. The
    scope check (404 if the policy/doc isn't the user's) is the only hard error.

    Images and scanned PDFs have no machine-readable text, so they yield
    ``indexed_chunks=0`` and a notes hint (OCR is a later phase).
    """
    # Hard scope check — raises 404 if the policy isn't accessible to this user.
    policy = await policy_service.get_policy(db, user, policy_id)
    doc = await db.get(PolicyDocument, document_id)
    if doc is None or doc.policy_id != policy.id:
        raise not_found("Document not found")

    out: dict = {
        "indexed_chunks": 0,
        "expiry_applied": False,
        "extracted": None,
        "notes": None,
    }

    # Download the file ONCE and reuse the bytes for both indexing and AI extraction
    # (previously fetched twice). A download failure degrades gracefully to a note.
    raw: bytes | None = None
    try:
        url = await storage.create_signed_download_url(doc.storage_path)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            raw = resp.content
    except Exception as exc:
        log.warning("auto_download_failed | doc=%s | %s", document_id, exc)
        out["notes"] = "Could not read this document."
        return out

    # 1) Index for Ask sVault (RAG). Lexical full-text — no embeddings provider.
    from app.services import rag_service

    try:
        out["indexed_chunks"] = await rag_service.index_bytes(db, doc, policy, raw)
    except Exception as exc:  # never let indexing failure break the flow
        log.warning("auto_index_failed | doc=%s | %s", document_id, exc)

    # 2) AI field extraction (text PDFs only) — reuses the bytes from above.
    from app.services import extraction_service

    try:
        result = await extraction_service.extract_policy_fields(raw, doc.mime_type, ai_key)
        out["extracted"] = result
        out["notes"] = result.get("notes")

        # 3) Auto-fill a missing expiry date so renewal alerts schedule themselves.
        expiry = result.get("expiry_date")
        if expiry and policy.expiry_date is None:
            try:
                policy.expiry_date = date.fromisoformat(expiry)
                await db.commit()
                out["expiry_applied"] = True
            except (ValueError, TypeError):
                pass  # malformed date from the model — ignore, leave policy unchanged
    except AppError as exc:
        # sVault AI not configured / unavailable — surface as a soft note.
        out["notes"] = exc.message if hasattr(exc, "message") else str(exc)
    except Exception as exc:
        log.warning("auto_extract_failed | doc=%s | %s", document_id, exc)
        out["notes"] = "Could not auto-read this document."

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
