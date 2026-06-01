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
import re
import uuid

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.security import CurrentUser
from app.db.models import PolicyDocument
from app.services import secrets_service
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


async def index_bytes(db: AsyncSession, doc: PolicyDocument, policy, raw: bytes) -> int:
    """(Re)index already-downloaded document ``raw`` bytes into document_chunks.

    Extracts text, chunks it, and replaces any existing chunks for the document.
    The CALLER is responsible for scope-checking ``doc``/``policy`` first. Lets the
    upload path reuse bytes it already downloaded (no second fetch). Returns the
    number of chunks stored (0 for non-PDF / unextractable documents).
    """
    text_content = _extract_text(raw, doc.mime_type)
    if not text_content.strip():
        return 0

    prefix = f"Policy: {policy.title} ({policy.category}) — " if policy else ""
    chunks = [prefix + c for c in chunk_text(text_content)]

    await db.execute(
        text("delete from document_chunks where document_id = :d"), {"d": str(doc.id)}
    )
    for c in chunks:
        await db.execute(
            text(
                "insert into document_chunks (tenant_id, org_id, policy_id, document_id, content)"
                " values (:t, :o, :p, :d, :c)"
            ),
            {"t": str(doc.tenant_id), "o": str(doc.org_id), "p": str(doc.policy_id),
             "d": str(doc.id), "c": c},
        )
    await db.commit()
    return len(chunks)


async def ingest_document(db: AsyncSession, user: CurrentUser, document_id: uuid.UUID) -> int:
    """Download a policy document, extract text, chunk it, store rows in document_chunks."""
    doc = await db.get(PolicyDocument, document_id)
    if doc is None:
        raise AppError(ErrorCode.not_found, "Document not found")
    # Object-level scope: the document's policy must be accessible to the caller
    # (tenant + org + owner). This closes a BOLA where a same-tenant user could pass
    # an accessible policy_id in the URL but a document_id from a policy in another
    # org / owned by someone else. Mirrors document_service.auto_process_document.
    from app.services import policy_service

    policy = await policy_service.get_policy(db, user, doc.policy_id)  # 404 if not scoped

    url = await storage.create_signed_download_url(doc.storage_path)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            raw = resp.content
    except httpx.HTTPError as exc:
        raise AppError(ErrorCode.upstream_error, "Could not read document") from exc

    return await index_bytes(db, doc, policy, raw)


async def _retrieve(db: AsyncSession, user: CurrentUser, question: str, limit: int = 8):
    org = _accessible_orgs(user)
    if org == "NONE":
        return []
    where = "tenant_id = :t"
    params: dict = {"t": user.tenant_id, "q": question, "k": limit}
    if org is not None:
        where += " and org_id = :o"
        params["o"] = str(org)
    # 1) Strict full-text: every query term must match (best relevance).
    rows = (await db.execute(text(
        f"select policy_id, content, ts_rank(to_tsvector('english', content),"
        f" plainto_tsquery('english', :q)) as rank from document_chunks where {where}"
        f" and to_tsvector('english', content) @@ plainto_tsquery('english', :q)"
        f" order by rank desc limit :k"), params)).all()
    if rows:
        return rows

    # 2) Looser full-text: ANY significant query word matches (OR). plainto_tsquery
    #    ANDs every term, so one off-vocabulary word yields nothing — this recovers
    #    paraphrased questions. Words are sanitised to alphanumerics (safe tsquery).
    words = [w for w in re.findall(r"[A-Za-z0-9]+", question.lower()) if len(w) > 2]
    if words:
        orq = " | ".join(words)
        rows = (await db.execute(text(
            f"select policy_id, content, ts_rank(to_tsvector('english', content),"
            f" to_tsquery('english', :orq)) as rank from document_chunks where {where}"
            f" and to_tsvector('english', content) @@ to_tsquery('english', :orq)"
            f" order by rank desc limit :k"), {**params, "orq": orq})).all()
        if rows:
            return rows

    # 3) Last resort: return the tenant's most recent chunks so general questions
    #    ("summarise my policies") still get grounded context. The system prompt
    #    constrains the model to answer only from this context, or say it can't.
    rows = (await db.execute(text(
        f"select policy_id, content, 0 as rank from document_chunks where {where}"
        f" order by created_at desc limit :k"), params)).all()
    return rows


async def ask(db: AsyncSession, user: CurrentUser, question: str) -> dict:
    # Resolve the key from platform_settings (Super-Admin console) → env fallback.
    api_key = await secrets_service.get_secret(
        db, "svault_ai_api_key", settings.svault_ai_api_key
    )
    if not api_key:
        raise AppError(ErrorCode.internal_error, "sVault AI is not configured")
    rows = await _retrieve(db, user, question)
    if not rows:
        return {"answer": "I couldn't find that in your policies.", "sources": []}

    context = "\n\n---\n\n".join(r.content for r in rows)
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=api_key, base_url=settings.svault_ai_base_url
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
