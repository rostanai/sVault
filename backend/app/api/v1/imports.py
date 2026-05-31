"""Bulk policy import endpoint (CSV / XLSX upload).

Thin router: auth, multipart parsing, delegation to data_io_service.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.errors import AppError, ErrorCode
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.reports import ImportResult
from app.services import data_io_service

router = APIRouter(tags=["imports"])

_create = require_permission("policy:create")


@router.post(
    "/policies/import",
    response_model=ImportResult,
    status_code=207,  # 207 Multi-Status: partial success is possible
    summary="Bulk-import policies from CSV or XLSX",
)
async def import_policies(
    file: UploadFile,
    org_id: str | None = Form(None, description="Target org UUID; defaults to caller's org"),
    user: CurrentUser = Depends(_create),
    db: AsyncSession = Depends(get_db),
) -> ImportResult:
    """Upload a CSV or XLSX file containing policies to create.

    - Accepted content-types: text/csv or OOXML spreadsheet (.xlsx).
    - Maximum 1 000 data rows; maximum 5 MB file size.
    - Header row is auto-detected (case-insensitive, space/underscore tolerant).
    - Dates may be Excel date values or YYYY-MM-DD strings.
    - Category must match a valid PolicyCategory value (normalised automatically).
    - Invalid rows are recorded in `errors` and skipped; the rest are created.
    - Returns {created, skipped, errors}.

    Requires policy:create permission.  Policies are tenant/org-scoped.
    """
    # --- Resolve target org ---
    if org_id:
        try:
            target_org_id = uuid.UUID(org_id)
        except ValueError as exc:
            raise AppError(ErrorCode.validation_error, "org_id must be a valid UUID") from exc
    elif user.org_id:
        target_org_id = uuid.UUID(user.org_id)
    else:
        raise AppError(
            ErrorCode.validation_error,
            "No org_id provided and caller has no default org. "
            "Pass org_id as a form field.",
        )

    # --- Read + size-check file bytes ---
    data = await file.read()
    if len(data) > data_io_service.MAX_FILE_BYTES:
        raise AppError(
            ErrorCode.validation_error,
            f"File exceeds maximum size of "
            f"{data_io_service.MAX_FILE_BYTES // (1024*1024)} MB.",
        )
    if len(data) == 0:
        raise AppError(ErrorCode.validation_error, "Uploaded file is empty.")

    # --- Detect format and parse ---
    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()

    is_xlsx = "xlsx" in filename or "spreadsheetml" in content_type or "excel" in content_type
    is_csv = "csv" in filename or "text/csv" in content_type

    if is_xlsx:
        raw_rows = data_io_service.parse_xlsx_bytes(data)
    elif is_csv or (not is_xlsx):
        # Default to CSV when content-type is generic (e.g. application/octet-stream)
        try:
            raw_rows = data_io_service.parse_csv_bytes(data)
        except Exception as exc:  # noqa: BLE001
            raise AppError(
                ErrorCode.validation_error,
                f"Could not parse file as CSV: {exc}",
            ) from exc
    else:
        raise AppError(
            ErrorCode.validation_error,
            "Unsupported file type. Upload a .csv or .xlsx file.",
        )

    created, skipped, errors = await data_io_service.run_import(
        db, user, raw_rows, target_org_id
    )

    return ImportResult(created=created, skipped=skipped, errors=errors)
