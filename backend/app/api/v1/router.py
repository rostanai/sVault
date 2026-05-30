"""v1 API router — aggregates feature routers (added per milestone)."""
from fastapi import APIRouter

from app.api.v1 import auth, health, invitations, orgs

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)          # M1
api_router.include_router(orgs.router)          # M1
api_router.include_router(invitations.router)   # M1

# Later milestones add routers here:
#   M2 policies/documents · M3 dashboard · M4 alerts · M5 billing/platform · M6 approvals
