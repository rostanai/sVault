"""Provider (insurer/vendor) endpoints (M2)."""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import get_current_user, require_permission
from app.core.security import CurrentUser
from app.db.models import Provider
from app.db.session import get_db
from app.schemas.policy import ProviderCreate, ProviderRead

router = APIRouter(prefix="/providers", tags=["providers"])

_manage = require_permission("provider:manage")


@router.get("", response_model=list[ProviderRead])
async def list_providers(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProviderRead]:
    stmt = select(Provider).where(Provider.tenant_id == uuid.UUID(user.tenant_id))
    return list((await db.execute(stmt)).scalars().all())


@router.post("", response_model=ProviderRead, status_code=201)
async def create_provider(
    payload: ProviderCreate,
    user: CurrentUser = Depends(_manage),
    db: AsyncSession = Depends(get_db),
) -> ProviderRead:
    provider = Provider(tenant_id=uuid.UUID(user.tenant_id), **payload.model_dump())
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider
