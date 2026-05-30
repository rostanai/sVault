"""v1 API router — aggregates feature routers (added per milestone)."""
from fastapi import APIRouter

from app.api.v1 import (
    alerts,
    auth,
    billing,
    dashboard,
    documents,
    health,
    invitations,
    orgs,
    platform,
    policies,
    providers,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)          # M1
api_router.include_router(orgs.router)          # M1
api_router.include_router(invitations.router)   # M1
api_router.include_router(policies.router)      # M2
api_router.include_router(providers.router)     # M2
api_router.include_router(documents.router)     # M2
api_router.include_router(alerts.router)        # M4
api_router.include_router(dashboard.router)     # M3
api_router.include_router(billing.router)       # M5
api_router.include_router(platform.router)      # M5

# Later milestones add routers here:
#   M6 approvals
