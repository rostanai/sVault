"""v1 API router — aggregates feature routers (added per milestone)."""
from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)

# Milestones add routers here:
#   M1 auth/org · M2 policies/documents · M3 dashboard · M4 alerts
#   M5 billing/platform · M6 approvals
