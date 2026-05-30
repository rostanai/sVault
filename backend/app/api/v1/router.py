"""v1 API router — aggregates feature routers (added per milestone)."""
from fastapi import APIRouter

from app.api.v1 import (
    auth,
    documents,
    health,
    invitations,
    orgs,
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

# Later milestones add routers here:
#   M3 dashboard · M4 alerts · M5 billing/platform · M6 approvals
