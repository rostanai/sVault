"""Ask sVault — RAG question-answering + document ingestion endpoints.

Endpoints
---------
POST /ask
    Plan-gated (requires "rag" entitlement).  Accepts a natural-language question
    and returns a Claude-generated answer grounded in the user's accessible policy
    documents, with source citations.

POST /policies/{policy_id}/documents/{document_id}/ingest
    Requires policy:read scope.  Triggers document chunking, embedding, and
    storage in document_chunks.  Idempotent.  Returns {chunks: N}.

Both endpoints require a valid Bearer token.  The RAG retrieval layer applies an
explicit tenant_id + org_id filter — RLS is NOT relied upon (backend runs as
service role).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.services import rag_service
from app.services.entitlements import require_entitlement

router = APIRouter(tags=["ask"])

# Module-level dep singletons (avoids ruff B008 default-arg call lint rule).
_need_rag = require_entitlement("rag")
_read = require_permission("policy:read")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)


class SourceRef(BaseModel):
    policy_id: str
    snippet: str


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceRef]


class IngestResponse(BaseModel):
    chunks: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/ask", response_model=AskResponse)
async def ask_svault(
    payload: AskRequest,
    user: CurrentUser = Depends(_need_rag),
    db: AsyncSession = Depends(get_db),
) -> AskResponse:
    """Answer a natural-language question using the user's accessible policy documents.

    Requires the "rag" plan entitlement.  The retrieval layer is explicitly
    scoped to the user's tenant + accessible orgs — never leaks cross-tenant data.
    """
    result = await rag_service.ask(db, user, payload.question)
    return AskResponse(
        answer=result["answer"],
        sources=[SourceRef(**s) for s in result["sources"]],
    )


@router.post(
    "/policies/{policy_id}/documents/{document_id}/ingest",
    response_model=IngestResponse,
    status_code=202,
)
async def ingest_document(
    policy_id: uuid.UUID,
    document_id: uuid.UUID,
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Chunk, embed, and index a policy document for RAG retrieval.

    Idempotent — re-ingesting the same document replaces its existing chunks.
    Requires policy:read permission (checks the policy is accessible to the user).
    The policy_id path parameter is validated for consistency but the definitive
    scope check is performed inside rag_service (PolicyDocument -> Policy lookup).
    Returns the number of chunks stored (0 for non-PDF / unextractable documents).
    """
    # Verify the user can access this policy (scope check; raises 404 if not)
    from app.services import policy_service
    await policy_service.get_policy(db, user, policy_id)

    count = await rag_service.ingest_document(db, user, document_id)
    return IngestResponse(chunks=count)
