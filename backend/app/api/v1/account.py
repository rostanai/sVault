"""DPDP account data-export endpoint.

GET /account/export — returns a downloadable JSON file containing the
caller's tenant data for a DPDP data-principal / portability request.

Permission choice
-----------------
Any authenticated tenant user may download their own tenant's export.
This follows the DPDP Act's 'data principal portability' right, which
applies to any data subject — not just admins.  We use `get_current_user`
(not `require_permission`) so all roles (admin / manager / owner / viewer)
may trigger an export.

Scoping is still applied server-side inside `build_export`:
  - Group-wide roles (admin/manager) see the whole tenant.
  - Owner/Viewer see only their org's policies and documents.
  - Tenant-level rows (Tenant, Organization, Profile) are always
    full-tenant so the user receives their context.

No secrets are included: API-key hashes, storage paths, platform
settings, and document file bytes are all excluded.
Cache-Control: no-store prevents proxies from caching personal data.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import get_current_user
from app.core.security import CurrentUser
from app.db.session import get_db
from app.services.account_export_service import build_export

router = APIRouter(prefix="/account", tags=["account"])


@router.get(
    "/export",
    summary="DPDP data-principal export",
    response_class=Response,
    responses={
        200: {
            "description": (
                "Downloadable JSON file containing the tenant's data snapshot "
                "(policies, providers, documents metadata, installments, approvals, "
                "org structure, team profiles).  No secrets or file bytes included."
            ),
            "content": {"application/json": {}},
        },
        401: {"description": "Missing or invalid bearer token"},
    },
)
async def export_account_data(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download a DPDP-compliant data export for the authenticated user's tenant.

    The response is a single JSON file attachment (`svault-data-export.json`).
    All fields are safe for portability:

    - UUIDs serialised as strings.
    - Decimal monetary values serialised as strings (preserves precision).
    - Dates and datetimes in ISO 8601 format.
    - No API-key material, no storage paths, no document bytes.

    Each collection object has an `items` array and a `_truncated` boolean
    (True when the result set was capped at 5,000 rows).

    **Permission:** any authenticated user (admin / manager / owner / viewer).
    Group-wide roles receive the full tenant's policies and documents;
    owner/viewer are scoped to their own organisation.
    """
    data = await build_export(db, user)
    content = json.dumps(data, indent=2, default=str)
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="svault-data-export.json"',
            "Cache-Control": "no-store",
        },
    )
