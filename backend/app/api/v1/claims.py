"""Claims endpoints.

Routes
------
GET    /claims                           list claims (cross-policy)               → 200
POST   /claims                           file a new claim                         → 201
GET    /claims/{claim_id}                get a single claim                       → 200
PATCH  /claims/{claim_id}                update claim fields / status             → 200
GET    /claims/{claim_id}/events         audit event log for a claim              → 200
GET    /policies/{policy_id}/claims      list claims for a specific policy        → 200

Authorization
-------------
* ``policy:read``   — GET routes (Admin, Manager, Owner, Viewer)
* ``policy:update`` — POST / PATCH (Admin, Manager, Owner)
* Object-level: Owner may only act on claims whose parent policy they own.
  Cross-tenant / non-owned → 404 (never 403) per ERROR_HANDLING.md.
"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require_permission
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.claim import ClaimCreate, ClaimEventRead, ClaimRead, ClaimUpdate
from app.services import claim_service

router = APIRouter(tags=["claims"])

# Module-level dep singletons — avoids ruff B008 (do-not-call-in-default-arg).
_read = require_permission("policy:read")
_update = require_permission("policy:update")


@router.get(
    "/claims",
    response_model=list[ClaimRead],
    summary="List claims",
)
async def list_claims(
    status: str | None = Query(
        None,
        description=(
            "Filter by status: draft | reported | under_review | "
            "approved | rejected | settled | closed"
        ),
    ),
    policy_id: uuid.UUID | None = Query(None, description="Filter by policy"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[ClaimRead]:
    """List claims accessible to the caller (tenant + org + owner scoped).

    Joins claims → policies to enforce object-level access for the *owner* role:
    only claims on the caller's own policies are returned.  Admin / Manager / Viewer
    see all claims in their org/group scope.

    Supports optional ``status`` and ``policy_id`` filters.  Results are newest-first.
    Cursor-compatible limit/offset pagination.
    """
    return await claim_service.list_claims(
        db, user, status=status, policy_id=policy_id, limit=limit, offset=offset
    )


@router.post(
    "/claims",
    response_model=ClaimRead,
    status_code=201,
    summary="File a new claim",
)
async def create_claim(
    payload: ClaimCreate,
    user: CurrentUser = Depends(_update),
    db: AsyncSession = Depends(get_db),
) -> ClaimRead:
    """File a new claim against an accessible policy.

    The referenced policy must be within the caller's tenant + org + owner scope —
    returns 404 otherwise (no existence leak).
    Inherits ``tenant_id`` and ``org_id`` from the policy.
    Defaults status to ``reported``; pass ``"draft"`` to save without submitting.
    An initial ``status_change`` ClaimEvent is written automatically.
    Requires ``policy:update`` (Admin, Manager, Owner).
    """
    return await claim_service.create(db, user, payload)


@router.get(
    "/claims/{claim_id}",
    response_model=ClaimRead,
    summary="Get a claim",
)
async def get_claim(
    claim_id: uuid.UUID,
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> ClaimRead:
    """Fetch a single claim by id.

    Returns 404 if the claim does not exist, belongs to a different tenant, or belongs
    to a policy the caller cannot access (object-level owner check).
    Requires ``policy:read``.
    """
    return await claim_service.get_claim(db, user, claim_id)


@router.patch(
    "/claims/{claim_id}",
    response_model=ClaimRead,
    summary="Update a claim",
)
async def update_claim(
    claim_id: uuid.UUID,
    payload: ClaimUpdate,
    user: CurrentUser = Depends(_update),
    db: AsyncSession = Depends(get_db),
) -> ClaimRead:
    """Partially update a claim.

    Any status transition is allowed in v1 (all → all).  A ``ClaimEvent`` with
    ``event_type="status_change"`` is written automatically when the status changes.
    The optional ``note`` field is recorded as an event alongside any update.
    Returns 404 if inaccessible.
    Requires ``policy:update``.
    """
    return await claim_service.update(db, user, claim_id, payload)


@router.get(
    "/claims/{claim_id}/events",
    response_model=list[ClaimEventRead],
    summary="List claim events",
)
async def list_claim_events(
    claim_id: uuid.UUID,
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[ClaimEventRead]:
    """Return the full audit event log for a claim, newest-first.

    Returns 404 if the claim is not accessible to the caller.
    Requires ``policy:read``.
    """
    return await claim_service.list_events(db, user, claim_id)


@router.get(
    "/policies/{policy_id}/claims",
    response_model=list[ClaimRead],
    summary="List claims for a policy",
)
async def list_claims_for_policy(
    policy_id: uuid.UUID,
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[ClaimRead]:
    """Return all claims filed against a specific policy, newest-first.

    The policy must be accessible to the caller (tenant + org + owner scoped).
    Returns 404 if the policy does not exist or is out of scope.
    Requires ``policy:read``.
    """
    return await claim_service.list_for_policy(db, user, policy_id)
