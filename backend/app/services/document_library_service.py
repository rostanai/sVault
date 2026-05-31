"""Document library service — cross-policy list + full-text/filename search.

No N+1: documents and matching chunks are resolved in two batched queries,
then mapped together before signed URLs are fetched (one per doc).
All queries are tenant_id + accessible-org scoped, mirroring
policy_service._accessible_org_filter.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.security import CurrentUser
from app.db.models.insurance import Policy, PolicyDocument
from app.schemas.document import DocumentLibraryItem
from app.services.org_service import is_group_wide
from app.services.policy_service import _owner_filter


def _accessible_org(user: CurrentUser) -> uuid.UUID | None:
    """None → whole tenant; UUID → single org."""
    if user.is_super_admin or is_group_wide(user.role):
        return None
    return uuid.UUID(user.org_id) if user.org_id else None


async def list_library(
    db: AsyncSession,
    user: CurrentUser,
    *,
    search: str | None = None,
    doc_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[DocumentLibraryItem]:
    """Return documents across all accessible policies with policy context.

    When *search* is provided:
    - Match file_name ILIKE %search%  OR
    - Match policy.title ILIKE %search%  OR
    - Match document_chunks via Postgres FTS (to_tsvector @@ plainto_tsquery).

    For the chunk-based matches, a ~160-char snippet is populated.
    Documents matched by filename/policy-title get snippet=None.
    """
    if not user.tenant_id:
        return []

    tid = user.tenant_id
    org = _accessible_org(user)

    # ------------------------------------------------------------------
    # Step 1: collect document + policy rows via a JOIN, applying scope
    # and optional metadata filters.  We always need the full set of
    # doc IDs before we can batch the chunk search.
    # ------------------------------------------------------------------
    stmt = (
        select(
            PolicyDocument.id,
            PolicyDocument.file_name,
            PolicyDocument.doc_type,
            PolicyDocument.mime_type,
            PolicyDocument.size_bytes,
            PolicyDocument.created_at,
            PolicyDocument.storage_path,
            PolicyDocument.policy_id,
            Policy.title.label("policy_title"),
            Policy.category.label("policy_category"),
        )
        .join(Policy, PolicyDocument.policy_id == Policy.id)
        .where(PolicyDocument.tenant_id == uuid.UUID(tid))
    )
    if org is not None:
        stmt = stmt.where(PolicyDocument.org_id == org)
    # Object-level: an owner sees only documents belonging to their own policies.
    owner_oid = _owner_filter(user)
    if owner_oid is not None:
        stmt = stmt.where(Policy.owner_id == owner_oid)
    if doc_type:
        stmt = stmt.where(PolicyDocument.doc_type == doc_type)

    # ------------------------------------------------------------------
    # Step 2: apply name/title filter when search is provided.
    # We pull ALL matching-by-name rows here (no limit yet) plus chunk
    # matches resolved separately.  Then dedupe + merge before paging.
    # ------------------------------------------------------------------
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            (PolicyDocument.file_name.ilike(like)) | (Policy.title.ilike(like))
        )

    stmt = stmt.order_by(PolicyDocument.created_at.desc())

    # For search we need all name/title matches + chunk matches before we
    # can dedupe; we can apply limit/offset after merging.
    if not search:
        stmt = stmt.limit(limit).offset(offset)

    rows = (await db.execute(stmt)).all()

    # Index by doc id for fast lookup.
    docs_by_id: dict[uuid.UUID, Any] = {r.id: r for r in rows}

    # ------------------------------------------------------------------
    # Step 3 (search only): chunk-based FTS / ILIKE for content hits.
    # Fetch best-ranked chunk per document, then map back.
    # ------------------------------------------------------------------
    chunk_snippets: dict[uuid.UUID, str] = {}

    if search:
        org_clause = "and dc.org_id = :o" if org is not None else ""
        params: dict[str, Any] = {"t": tid, "search": search, "k": 200}
        if org is not None:
            params["o"] = str(org)

        # FTS rank — best chunk per document (DISTINCT ON)
        fts_sql = text(
            f"""
            select distinct on (dc.document_id)
                dc.document_id,
                dc.content,
                ts_rank(to_tsvector('english', dc.content),
                        plainto_tsquery('english', :search)) as rank
            from document_chunks dc
            where dc.tenant_id = :t
              {org_clause}
              and to_tsvector('english', dc.content)
                  @@ plainto_tsquery('english', :search)
            order by dc.document_id, rank desc
            limit :k
            """
        )
        fts_rows = (await db.execute(fts_sql, params)).all()

        if not fts_rows:
            # Fallback: ILIKE on chunk content
            ilike_sql = text(
                f"""
                select distinct on (dc.document_id)
                    dc.document_id,
                    dc.content,
                    0 as rank
                from document_chunks dc
                where dc.tenant_id = :t
                  {org_clause}
                  and dc.content ilike :like
                order by dc.document_id, dc.created_at desc
                limit :k
                """
            )
            fts_rows = (await db.execute(ilike_sql, {**params, "like": f"%{search[:80]}%"})).all()

        # Resolve missing docs (chunk match without name/title match) via a second
        # targeted JOIN so we don't miss them.
        chunk_doc_ids = {r.document_id for r in fts_rows}
        missing_ids = chunk_doc_ids - set(docs_by_id.keys())

        if missing_ids:
            extra_stmt = (
                select(
                    PolicyDocument.id,
                    PolicyDocument.file_name,
                    PolicyDocument.doc_type,
                    PolicyDocument.mime_type,
                    PolicyDocument.size_bytes,
                    PolicyDocument.created_at,
                    PolicyDocument.storage_path,
                    PolicyDocument.policy_id,
                    Policy.title.label("policy_title"),
                    Policy.category.label("policy_category"),
                )
                .join(Policy, PolicyDocument.policy_id == Policy.id)
                .where(
                    PolicyDocument.tenant_id == uuid.UUID(tid),
                    PolicyDocument.id.in_(list(missing_ids)),
                )
            )
            if org is not None:
                extra_stmt = extra_stmt.where(PolicyDocument.org_id == org)
            if owner_oid is not None:
                extra_stmt = extra_stmt.where(Policy.owner_id == owner_oid)
            if doc_type:
                extra_stmt = extra_stmt.where(PolicyDocument.doc_type == doc_type)
            for extra_row in (await db.execute(extra_stmt)).all():
                docs_by_id[extra_row.id] = extra_row

        # Build snippet map (trim to ~160 chars at word boundary).
        for r in fts_rows:
            content = r.content or ""
            snippet = content[:160].rsplit(" ", 1)[0] if len(content) > 160 else content
            chunk_snippets[r.document_id] = snippet

        # Re-sort merged set: chunk hits first (ranked), then name/title hits
        chunk_order = [r.document_id for r in fts_rows if r.document_id in docs_by_id]
        non_chunk = [d for d in docs_by_id.keys() if d not in chunk_snippets]
        ordered_ids = chunk_order + [d for d in non_chunk if d not in chunk_order]
        docs_by_id = {did: docs_by_id[did] for did in ordered_ids if did in docs_by_id}

        # Apply pagination after merge.
        all_docs = list(docs_by_id.values())
        all_docs = all_docs[offset: offset + limit]
        docs_by_id = {d.id: d for d in all_docs}

    # ------------------------------------------------------------------
    # Step 4: fetch signed download URLs (one per doc) and build items.
    # ------------------------------------------------------------------
    # Sign all download URLs concurrently rather than serially. return_exceptions
    # preserves the per-doc tolerance (storage unreachable in tests/dev → empty URL).
    doc_rows = list(docs_by_id.values())
    signed = await asyncio.gather(
        *(storage.create_signed_download_url(d.storage_path) for d in doc_rows),
        return_exceptions=True,
    )
    items: list[DocumentLibraryItem] = [
        DocumentLibraryItem(
            id=doc_row.id,
            file_name=doc_row.file_name,
            doc_type=doc_row.doc_type,
            mime_type=doc_row.mime_type,
            size_bytes=doc_row.size_bytes,
            created_at=doc_row.created_at,
            download_url="" if isinstance(url, BaseException) else url,
            policy_id=doc_row.policy_id,
            policy_title=doc_row.policy_title,
            policy_category=doc_row.policy_category,
            snippet=chunk_snippets.get(doc_row.id),
        )
        for doc_row, url in zip(doc_rows, signed, strict=True)
    ]
    return items
