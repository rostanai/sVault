"""Installment service — business logic for policy premium instalment tracking.

Defense-in-depth notes
-----------------------
* Policy access is verified via policy_service.get_policy (tenant + org scoped; raises
  404 for cross-tenant or non-accessible policies — never 403, so IDs are not revealed).
* Instalment queries are additionally scoped by tenant_id to prevent cross-tenant leakage
  even if an instalment_id is guessed correctly.
* No FastAPI imports — this is pure business logic consumable from tests / CLI.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import not_found
from app.core.security import CurrentUser
from app.db.models.installments import Installment
from app.schemas.installment import InstallmentCreate
from app.services import policy_service


async def list_for_policy(
    db: AsyncSession,
    user: CurrentUser,
    policy_id: uuid.UUID,
) -> list[Installment]:
    """Return all instalments for a policy, ordered by due_date asc.

    Verifies the policy is accessible to the caller (404 if not).
    """
    # scope-check: raises not_found if policy is inaccessible / cross-tenant
    policy = await policy_service.get_policy(db, user, policy_id)

    stmt = (
        select(Installment)
        .where(
            Installment.policy_id == policy.id,
            Installment.tenant_id == uuid.UUID(user.tenant_id),
        )
        .order_by(Installment.due_date.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create(
    db: AsyncSession,
    user: CurrentUser,
    policy_id: uuid.UUID,
    payload: InstallmentCreate,
) -> Installment:
    """Create a new pending instalment for an accessible policy.

    Inherits tenant_id from the policy row (not blindly from the JWT) so that
    parent-admin roll-up scenarios correctly inherit subsidiary tenant scope.
    """
    policy = await policy_service.get_policy(db, user, policy_id)

    installment = Installment(
        tenant_id=policy.tenant_id,
        policy_id=policy.id,
        amount_inr=payload.amount_inr,
        due_date=payload.due_date,
        status="pending",
        note=payload.note,
    )
    db.add(installment)
    await db.commit()
    await db.refresh(installment)
    return installment


async def mark_paid(
    db: AsyncSession,
    user: CurrentUser,
    installment_id: uuid.UUID,
) -> Installment:
    """Mark an instalment as paid.

    Sets status='paid' and paid_at=now(UTC).
    Returns 404 for missing or cross-tenant records (never 403).
    """
    installment = await _load_installment(db, user, installment_id)
    installment.status = "paid"
    installment.paid_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(installment)
    return installment


async def delete(
    db: AsyncSession,
    user: CurrentUser,
    installment_id: uuid.UUID,
) -> None:
    """Delete an instalment (tenant-scoped; 404 for cross-tenant or missing)."""
    installment = await _load_installment(db, user, installment_id)
    await db.delete(installment)
    await db.commit()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _load_installment(
    db: AsyncSession,
    user: CurrentUser,
    installment_id: uuid.UUID,
) -> Installment:
    """Load an instalment scoped to the caller's tenant; 404 if not found."""
    if not user.tenant_id:
        raise not_found("Installment not found")

    stmt = select(Installment).where(
        Installment.id == installment_id,
        Installment.tenant_id == uuid.UUID(user.tenant_id),
    )
    installment = (await db.execute(stmt)).scalar_one_or_none()
    if installment is None:
        raise not_found("Installment not found")
    return installment
