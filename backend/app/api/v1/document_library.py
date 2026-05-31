"""Document library endpoint — cross-policy document list + search.

GET /documents

Returns every document the authenticated caller can access, joined with
policy context.  Optional full-text / filename / policy-title search.
Scoped to the caller's tenant + accessible orgs.  Signed download URLs
are included in each item (reuses the same storage helper as documents.py).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.document import DocumentLibraryItem
from app.services import document_library_service

router = APIRouter(tags=["document-library"])

_read = require_permission("policy:read")


@router.get(
    "/documents",
    response_model=list[DocumentLibraryItem],
    summary="List all accessible documents across policies",
)
async def list_document_library(
    search: Annotated[
        str | None,
        Query(
            description=(
                "Optional search string. Matches file name, policy title, or document content "
                "(full-text search on ingested chunks). When a content match is the reason a "
                "document is included, a ~160-char snippet is populated."
            ),
            max_length=200,
        ),
    ] = None,
    doc_type: Annotated[
        str | None,
        Query(
            description=(
                "Filter by document type "
                "(policy, schedule, endorsement, invoice, claim, other)."
            )
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Page size (max 200).")] = 50,
    offset: Annotated[int, Query(ge=0, description="Pagination offset.")] = 0,
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentLibraryItem]:
    """List every document the caller can access, across all their policies.

    Documents are ordered by created_at descending (newest first).
    When *search* is provided the order changes to: content matches first
    (by FTS rank), then filename/policy-title matches.

    - **search**: matched against file_name ILIKE, policy title ILIKE, and
      document_chunks FTS (`to_tsvector @@ plainto_tsquery`).
    - **doc_type**: filter by document type.
    - **limit/offset**: standard pagination.

    Authorization: requires `policy:read` permission.  Only documents
    belonging to the caller's tenant and accessible org(s) are returned.
    Cross-tenant access returns an empty list (not 403).
    """
    return await document_library_service.list_library(
        db,
        user,
        search=search,
        doc_type=doc_type,
        limit=limit,
        offset=offset,
    )
