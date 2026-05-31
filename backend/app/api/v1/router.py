"""v1 API router — aggregates feature routers (added per milestone)."""
from fastapi import APIRouter

from app.api.v1 import (
    alerts,
    api_keys,
    approvals,
    ask,
    auth,
    billing,
    dashboard,
    documents,
    exports,
    health,
    imports,
    intake,
    invitations,
    orgs,
    platform,
    policies,
    providers,
    public,
    reports,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)          # M1
api_router.include_router(orgs.router)          # M1
api_router.include_router(invitations.router)   # M1
api_router.include_router(users.router)         # team/user management
api_router.include_router(policies.router)      # M2
api_router.include_router(providers.router)     # M2
api_router.include_router(documents.router)     # M2
api_router.include_router(alerts.router)        # M4
api_router.include_router(dashboard.router)     # M3
api_router.include_router(billing.router)       # M5
api_router.include_router(platform.router)      # M5

api_router.include_router(approvals.router)     # M6 approvals
api_router.include_router(ask.router)           # AI "Ask sVault" (RAG)
api_router.include_router(intake.router)        # AI policy auto-intake (extract)
api_router.include_router(api_keys.router)      # M7 developer API key management
api_router.include_router(public.router)        # M7 public developer API (API-key auth)
api_router.include_router(exports.router)       # policy + renewal export (CSV/XLSX)
api_router.include_router(imports.router)       # bulk policy import (CSV/XLSX)
api_router.include_router(reports.router)       # renewal report (JSON)
