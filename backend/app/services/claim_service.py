"""Claim service — business logic for the claims module.

Defense-in-depth notes
-----------------------
* **Object-level access** (BOLA defence): claims carry no owner_id of their own;
  ownership is inherited from the parent policy (``policies.owner_id``).  To enforce
  this we:

  1. For CREATE and single-claim GET/PATCH: call ``policy_service.get_policy`` which
     already enforces tenant + org + owner scope; a non-accessible policy → 404.

  2. For the cross-policy LIST: join ``claims`` → ``policies`` and apply:
     - ``claims.tenant_id == user.tenant_id``               (always)
     - ``policies.org_id == _accessible_org_filter(user)``  (if not None)
     - ``policies.owner_id == _owner_filter(user)``         (if not None — owner role)
     This mirrors exactly the scope applied by ``policy_service.list_policies``.

* Tenant + org scoping is always applied; never replaced.
* Cross-tenant or non-accessible claim_id → 404 (never 403) per ERROR_HANDLING.md.
* No FastAPI imports — pure business logic.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import not_found
from app.core.security import CurrentUser
from app.db.models.claims import Claim, ClaimEvent
from app.db.models.insurance import Policy
from app.schemas.claim import ClaimCreate, ClaimRead, ClaimUpdate
from app.services import policy_service
from app.services.policy_service import (
    _accessible_org_filter,
    _owner_filter,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _enrich(claim: Claim, policy_title: str | None) -> ClaimRead:
    """Build a ``ClaimRead`` from an ORM object, injecting the enriched policy_title."""
    data = ClaimRead.model_validate(claim)
    data.policy_title = policy_title
    return data


async def _load_claim_scoped(
    db: AsyncSession,
    user: CurrentUser,
    claim_id: uuid.UUID,
) -> tuple[Claim, str | None]:
    """Load a claim with full scope enforcement via a policy JOIN.

    Applies:
    - claims.tenant_id == user.tenant_id
    - policies.org_id == _accessible_org_filter(user)  (if not None)
    - policies.owner_id == _owner_filter(user)         (if not None)

    Returns (claim, policy_title).  Raises not_found for any miss (cross-tenant,
    cross-org, wrong owner, or genuinely absent row).
    """
    if not user.tenant_id:
        raise not_found("Claim not found")

    stmt = (
        select(Claim, Policy.title)
        .join(Policy, Policy.id == Claim.policy_id)
        .where(
            Claim.id == claim_id,
            Claim.tenant_id == uuid.UUID(user.tenant_id),
        )
    )

    org = _accessible_org_filter(user)
    if org is not None:
        stmt = stmt.where(Policy.org_id == org)

    owner_uid = _owner_filter(user)
    if owner_uid is not None:
        stmt = stmt.where(Policy.owner_id == owner_uid)

    row = (await db.execute(stmt)).first()
    if row is None:
        raise not_found("Claim not found")

    claim, policy_title = row
    return claim, policy_title


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create(
    db: AsyncSession,
    user: CurrentUser,
    payload: ClaimCreate,
) -> ClaimRead:
    """Create a new claim on a scope-verified policy.

    - Verifies the policy is accessible (tenant + org + owner) via get_policy (→ 404 if not).
    - Inherits tenant_id and org_id from the policy row.
    - Defaults status to "reported" unless the caller explicitly passes "draft".
    - Writes an initial ClaimEvent (status_change, to_status=chosen status).
    - Returns a ClaimRead enriched with policy_title.
    """
    # Scope-check: raises not_found for inaccessible / cross-tenant policy.
    policy = await policy_service.get_policy(db, user, payload.policy_id)
    # Cache title before the commit expires the policy object.
    policy_title: str | None = policy.title

    claim = Claim(
        tenant_id=policy.tenant_id,
        org_id=policy.org_id,
        policy_id=policy.id,
        claim_number=payload.claim_number,
        status=payload.status,
        claim_amount_inr=payload.claim_amount_inr,
        incident_date=payload.incident_date,
        reported_date=date.today() if payload.status != "draft" else None,
        description=payload.description,
        created_by=uuid.UUID(user.user_id),
    )
    db.add(claim)
    await db.flush()  # assign claim.id before creating the event

    event = ClaimEvent(
        tenant_id=policy.tenant_id,
        claim_id=claim.id,
        event_type="status_change",
        from_status=None,
        to_status=claim.status,
        note="Claim created",
        created_by=uuid.UUID(user.user_id),
    )
    db.add(event)
    await db.commit()
    await db.refresh(claim)
    return _enrich(claim, policy_title)


async def list_claims(
    db: AsyncSession,
    user: CurrentUser,
    *,
    status: str | None = None,
    policy_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ClaimRead]:
    """List claims visible to the caller with optional status/policy filters.

    Object-level scoping applied via JOIN to policies:
    - tenant_id always filtered on claims.
    - org scope applied on policies.org_id (_accessible_org_filter).
    - owner scope applied on policies.owner_id (_owner_filter) — owner role only.

    Returns newest-first, enriched with policy_title.
    """
    if not user.tenant_id:
        return []

    stmt = (
        select(Claim, Policy.title)
        .join(Policy, Policy.id == Claim.policy_id)
        .where(Claim.tenant_id == uuid.UUID(user.tenant_id))
    )

    org = _accessible_org_filter(user)
    if org is not None:
        stmt = stmt.where(Policy.org_id == org)

    owner_uid = _owner_filter(user)
    if owner_uid is not None:
        stmt = stmt.where(Policy.owner_id == owner_uid)

    if status is not None:
        stmt = stmt.where(Claim.status == status)

    if policy_id is not None:
        stmt = stmt.where(Claim.policy_id == policy_id)

    stmt = stmt.order_by(Claim.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).all()
    return [_enrich(claim, title) for claim, title in rows]


async def get_claim(
    db: AsyncSession,
    user: CurrentUser,
    claim_id: uuid.UUID,
) -> ClaimRead:
    """Return a single scoped claim enriched with policy_title; 404 if inaccessible."""
    claim, policy_title = await _load_claim_scoped(db, user, claim_id)
    return _enrich(claim, policy_title)


async def update(
    db: AsyncSession,
    user: CurrentUser,
    claim_id: uuid.UUID,
    payload: ClaimUpdate,
) -> ClaimRead:
    """Partially update a claim.

    - Applies all set fields.
    - If status changes, writes a ClaimEvent (event_type="status_change",
      from_status=old, to_status=new) carrying any provided note.
    - updated_at is refreshed via SQLAlchemy's onupdate hook.
    - Returns the enriched ClaimRead.
    """
    claim, policy_title = await _load_claim_scoped(db, user, claim_id)

    updates = payload.model_dump(exclude_unset=True, exclude={"note"})
    old_status = claim.status

    for field, value in updates.items():
        setattr(claim, field, value)

    new_status = claim.status
    status_changed = "status" in updates and old_status != new_status

    if status_changed or payload.note:
        event = ClaimEvent(
            tenant_id=claim.tenant_id,
            claim_id=claim.id,
            event_type="status_change" if status_changed else "note",
            from_status=old_status if status_changed else None,
            to_status=new_status if status_changed else None,
            note=payload.note,
            created_by=uuid.UUID(user.user_id),
        )
        db.add(event)

    # Touch updated_at explicitly (SQLAlchemy onupdate only fires on UPDATE, not flush).
    claim.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(claim)
    return _enrich(claim, policy_title)


async def list_events(
    db: AsyncSession,
    user: CurrentUser,
    claim_id: uuid.UUID,
) -> list[ClaimEvent]:
    """Return audit events for a claim, newest-first.

    Verifies claim accessibility via _load_claim_scoped (→ 404 if not accessible).
    """
    claim, _ = await _load_claim_scoped(db, user, claim_id)

    stmt = (
        select(ClaimEvent)
        .where(ClaimEvent.claim_id == claim.id)
        .order_by(ClaimEvent.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_for_policy(
    db: AsyncSession,
    user: CurrentUser,
    policy_id: uuid.UUID,
) -> list[ClaimRead]:
    """Return all claims for a specific policy, newest-first.

    Verifies the policy is accessible via get_policy (→ 404 if not) then fetches claims.
    """
    policy = await policy_service.get_policy(db, user, policy_id)
    policy_title: str | None = policy.title  # cache before any further async ops

    stmt = (
        select(Claim)
        .where(
            Claim.policy_id == policy.id,
            Claim.tenant_id == uuid.UUID(user.tenant_id),
        )
        .order_by(Claim.created_at.desc())
    )
    result = await db.execute(stmt)
    claims = list(result.scalars().all())
    return [_enrich(c, policy_title) for c in claims]
