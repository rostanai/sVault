"""AI "Ask sVault" — grounded Q&A over the tenant's policy documents.

Retrieval is **lexical** (Postgres full-text over document text) — no embeddings
provider needed. Generation uses the configured OpenAI-compatible LLM ("sVault AI").
The provider name is never surfaced to users. Permission-safe: queries are filtered
EXPLICITLY by tenant_id + accessible orgs (the backend connects as the service role,
so RLS does not auto-apply — mirror policy_service scoping).
"""
from __future__ import annotations

import io
import logging
import uuid

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.security import CurrentUser
from app.db.models import Policy, PolicyDocument
from app.services.org_service import is_group_wide

log = logging.getLogger("svault.rag")

SYSTEM_PROMPT = (
    "You are sVault AI, an assistant that answers questions strictly from the user's "
    "insurance policy documents provided below as context. Only use the context. "
    "Cite the policy title when you answer. If the context does not contain the answer, "
    'say "I couldn\'t find that in your policies." Never invent details. Be concise.'
)


def chunk_text(content: str, size: int = 800, overlap: int = 100) -> list[str]:
    """Split text into ~`size`-word windows with `overlap` words of context."""
    words = content.split()
    if not words:
        return []
    chunks, start = [], 0
    while start < len(words):
        chunk = " ".join(words[start : start + size])
        if chunk.strip():
            chunks.append(chunk)
        start += max(1, size - overlap)
    return chunks


def _accessible_orgs(user: CurrentUser):
    """None => whole tenant (admin/manager/super); 'NONE' => no access; else the user's org."""
    if user.is_super_admin or is_group_wide(user.role):
        return None
    return uuid.UUID(user.org_id) if user.org_id else "NONE"


def _extract_text(raw: bytes, mime: str | None) -> str:
    if mime and "pdf" not in mime:
        return ""  # images/others: skip (OCR is a later phase)
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # pragma: no cover
        log.warning("pdf_extract_failed: %s", exc)
        return ""


async def ingest_document(db: AsyncSession, user: CurrentUser, document_id: uuid.UUID) -> int:
    """Download a policy document, extract text, chunk it, store rows in document_chunks."""
    doc = await db.get(PolicyDocument, document_id)
    if doc is None or str(doc.tenant_id) != user.tenant_id:
        raise AppError(ErrorCode.not_found, "Document not found")
    policy = await db.get(Policy, doc.policy_id)

    url = await storage.create_signed_download_url(doc.storage_path)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            raw = resp.content
    except httpx.HTTPError as exc:
        raise AppError(ErrorCode.upstream_error, "Could not read document") from exc

    text_content = _extract_text(raw, doc.mime_type)
    if not text_content.strip():
        return 0

    prefix = f"Policy: {policy.title} ({policy.category}) — " if policy else ""
    chunks = [prefix + c for c in chunk_text(text_content)]

    await db.execute(
        text("delete from document_chunks where document_id = :d"), {"d": str(document_id)}
    )
    for c in chunks:
        await db.execute(
            text(
                "insert into document_chunks (tenant_id, org_id, policy_id, document_id, content)"
                " values (:t, :o, :p, :d, :c)"
            ),
            {"t": str(doc.tenant_id), "o": str(doc.org_id), "p": str(doc.policy_id),
             "d": str(document_id), "c": c},
        )
    await db.commit()
    return len(chunks)


async def _retrieve(db: AsyncSession, user: CurrentUser, question: str, limit: int = 8):
    org = _accessible_orgs(user)
    if org == "NONE":
        return []
    where = "tenant_id = :t"
    params: dict = {"t": user.tenant_id, "q": question, "k": limit}
    if org is not None:
        where += " and org_id = :o"
        params["o"] = str(org)
    rows = (await db.execute(text(
        f"select policy_id, content, ts_rank(to_tsvector('english', content),"
        f" plainto_tsquery('english', :q)) as rank from document_chunks where {where}"
        f" and to_tsvector('english', content) @@ plainto_tsquery('english', :q)"
        f" order by rank desc limit :k"), params)).all()
    if not rows:
        rows = (await db.execute(text(
            f"select policy_id, content, 0 as rank from document_chunks where {where}"
            f" and content ilike :like order by created_at desc limit :k"),
            {**params, "like": f"%{question[:60]}%"})).all()
    return rows


async def ask(db: AsyncSession, user: CurrentUser, question: str) -> dict:
    if not settings.svault_ai_api_key:
        raise AppError(ErrorCode.internal_error, "sVault AI is not configured")
    rows = await _retrieve(db, user, question)
    if not rows:
        return {"answer": "I couldn't find that in your policies.", "sources": []}

    context = "\n\n---\n\n".join(r.content for r in rows)
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.svault_ai_api_key, base_url=settings.svault_ai_base_url
        )
        resp = await client.chat.completions.create(
            model=settings.svault_ai_model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nContext:\n{context}"},
                {"role": "user", "content": question},
            ],
        )
        answer = resp.choices[0].message.content or ""
    except Exception as exc:
        log.warning("svault_ai_failed: %s", exc)
        raise AppError(ErrorCode.upstream_error, "sVault AI is unavailable") from exc

    sources = [{"policy_id": str(r.policy_id), "snippet": r.content[:200]} for r in rows[:4]]
    return {"answer": answer, "sources": sources}
