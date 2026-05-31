"""Policy auto-intake endpoint — AI-assisted field extraction from a PDF upload.

Endpoint
--------
POST /policies/extract
    Upload a policy PDF; sVault AI returns a structured extraction for the user
    to review. Nothing is persisted — the user then calls POST /policies to save.

Auth: requires a valid Bearer token and the ``policy:create`` permission.
Plan: no entitlement gate (extraction is a creation assist, not a separate feature).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.intake import PolicyExtraction
from app.services import extraction_service, secrets_service

router = APIRouter(tags=["intake"])

# Module-level dep singletons — avoids ruff B008 default-arg call lint rule.
_can_create = require_permission("policy:create")
# File(...) is a FastAPI FieldInfo marker, not a side-effectful call; but ruff B008
# still triggers for it in default position, so we hoist it here.
_pdf_file: UploadFile = File(..., description="Policy PDF file (max 20 MB).")

_MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post(
    "/policies/extract",
    response_model=PolicyExtraction,
    status_code=200,
    summary="Extract policy fields from a PDF",
)
async def extract_policy(
    file: UploadFile = _pdf_file,
    user: CurrentUser = Depends(_can_create),
    db: AsyncSession = Depends(get_db),
) -> PolicyExtraction:
    """Upload a policy PDF and receive AI-extracted structured fields for review.

    sVault AI reads the document text and returns best-effort values for
    category, policy number, insurer, dates, and financial amounts. All fields
    are nullable — the user must review before saving via POST /policies.

    Rejects non-machine-readable (scanned) PDFs gracefully with a note.
    Does NOT persist anything.
    """
    raw = await file.read()

    if len(raw) > _MAX_FILE_BYTES:
        raise AppError(
            ErrorCode.validation_error,
            f"File exceeds the 20 MB limit (received {len(raw) // (1024 * 1024)} MB).",
        )

    api_key = await secrets_service.get_secret(
        db, "svault_ai_api_key", settings.svault_ai_api_key
    )
    result = await extraction_service.extract_policy_fields(
        raw, file.content_type, api_key=api_key
    )
    return PolicyExtraction(**result)
