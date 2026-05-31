"""Alert rule config + alert listing (scope-checked). Dispatch lives in alert_engine."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.db.models import Alert, AlertRule, Policy
from app.schemas.alert import AlertRuleRead, AlertRuleUpdate
from app.services.alert_engine import DEFAULT_CHANNELS, DEFAULT_LEAD_DAYS
from app.services.policy_service import _accessible_org_filter, _owner_filter, get_policy


async def get_effective_rule(
    db: AsyncSession, user: CurrentUser, policy_id: uuid.UUID
) -> AlertRuleRead:
    await get_policy(db, user, policy_id)  # scope-checked (404 if not accessible)
    rule = (
        await db.execute(
            select(AlertRule).where(
                AlertRule.policy_id == policy_id,
                AlertRule.tenant_id == uuid.UUID(user.tenant_id),
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        return AlertRuleRead(
            id=None, policy_id=policy_id, lead_days=DEFAULT_LEAD_DAYS,
            channels=DEFAULT_CHANNELS, escalate=True, is_active=True,
        )
    return AlertRuleRead.model_validate(rule, from_attributes=True)


async def upsert_rule(
    db: AsyncSession, user: CurrentUser, policy_id: uuid.UUID, payload: AlertRuleUpdate
) -> AlertRuleRead:
    await get_policy(db, user, policy_id)  # scope-checked
    rule = (
        await db.execute(
            select(AlertRule).where(
                AlertRule.policy_id == policy_id,
                AlertRule.tenant_id == uuid.UUID(user.tenant_id),
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        rule = AlertRule(tenant_id=uuid.UUID(user.tenant_id), policy_id=policy_id)
        db.add(rule)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return AlertRuleRead.model_validate(rule, from_attributes=True)


async def list_alerts(
    db: AsyncSession, user: CurrentUser, *, status: str | None = None,
    limit: int = 50, offset: int = 0,
) -> list[Alert]:
    stmt = select(Alert).where(Alert.tenant_id == uuid.UUID(user.tenant_id))
    org = _accessible_org_filter(user)
    if org is not None:
        stmt = stmt.where(Alert.org_id == org)
    # Object-level: an owner sees alerts only for the policies they own. Alerts carry
    # no owner_id, so restrict to alerts whose policy is owned by the user.
    if (oid := _owner_filter(user)) is not None:
        stmt = stmt.where(
            Alert.policy_id.in_(select(Policy.id).where(Policy.owner_id == oid))
        )
    if status:
        stmt = stmt.where(Alert.status == status)
    stmt = stmt.order_by(Alert.scheduled_for.desc()).limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all())
