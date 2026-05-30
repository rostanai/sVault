"""Alert engine endpoints (M4) — rule config, listing, ack, cron dispatch."""
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import get_current_user, require_permission
from app.core.config import settings
from app.core.errors import not_found
from app.core.security import CurrentUser
from app.db.session import get_db
from app.schemas.alert import (
    AlertRead,
    AlertRuleRead,
    AlertRuleUpdate,
    DispatchSummary,
)
from app.services import alert_engine, alert_service

router = APIRouter(tags=["alerts"])

_read = require_permission("policy:read")
_configure = require_permission("alert:configure")


def verify_cron(request: Request) -> None:
    """Machine-only endpoint guard — pg_cron/Vercel Cron sends X-Cron-Secret."""
    secret = request.headers.get("X-Cron-Secret", "")
    if not settings.cron_secret or secret != settings.cron_secret:
        raise not_found("Not found")  # 404 hides the endpoint


@router.get("/policies/{policy_id}/alert-rule", response_model=AlertRuleRead)
async def get_alert_rule(
    policy_id: uuid.UUID,
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> AlertRuleRead:
    return await alert_service.get_effective_rule(db, user, policy_id)


@router.put("/policies/{policy_id}/alert-rule", response_model=AlertRuleRead)
async def set_alert_rule(
    policy_id: uuid.UUID,
    payload: AlertRuleUpdate,
    user: CurrentUser = Depends(_configure),
    db: AsyncSession = Depends(get_db),
) -> AlertRuleRead:
    return await alert_service.upsert_rule(db, user, policy_id, payload)


@router.get("/alerts", response_model=list[AlertRead])
async def list_alerts(
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(_read),
    db: AsyncSession = Depends(get_db),
) -> list[AlertRead]:
    return await alert_service.list_alerts(db, user, status=status, limit=limit, offset=offset)


@router.post("/alerts/{alert_id}/ack")
async def acknowledge_alert(
    alert_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    alert = await alert_engine.acknowledge(db, user.user_id, alert_id)
    if alert is None:
        raise not_found("Alert not found")
    return {"id": str(alert.id), "status": alert.status}


@router.post(
    "/alerts/dispatch",
    response_model=DispatchSummary,
    dependencies=[Depends(verify_cron)],  # runs before get_db
)
async def dispatch_alerts(db: AsyncSession = Depends(get_db)) -> DispatchSummary:
    """Cron-triggered (NOT user-facing): scan due policies and send alerts."""
    summary = await alert_engine.scan_and_dispatch(db)
    return DispatchSummary(**summary)
