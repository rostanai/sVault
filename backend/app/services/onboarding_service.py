"""Onboarding status service — first-run checklist computed from live counts.

Computes which first-run steps the tenant has completed by running cheap
COUNT queries scoped to the caller's tenant (and accessible orgs where the
model carries org_id, mirroring policy_service scoping).

No FastAPI imports — pure business logic.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.db.models.alerts import Alert, AlertRule
from app.db.models.insurance import Policy, PolicyDocument, Provider
from app.db.models.tenancy import Invitation, Profile
from app.schemas.onboarding import OnboardingStatus, OnboardingStep
from app.services.org_service import is_group_wide

# ---------------------------------------------------------------------------
# Step definitions — static metadata (key, label, description, href)
# ---------------------------------------------------------------------------

_STEPS: list[dict] = [
    {
        "key": "provider",
        "label": "Add an insurer/provider",
        "description": "Add at least one insurer or provider to start tracking policies.",
        "href": "/app/providers",
    },
    {
        "key": "policy",
        "label": "Add your first policy",
        "description": "Create your first insurance policy record.",
        "href": "/app/policies",
    },
    {
        "key": "document",
        "label": "Upload a policy document",
        "description": "Attach a policy document so your vault is complete.",
        "href": "/app/policies",
    },
    {
        "key": "alert",
        "label": "Set up renewal alerts",
        "description": "Configure multi-channel alerts so renewals are never missed.",
        "href": "/app/alerts",
    },
    {
        "key": "team",
        "label": "Invite a teammate",
        "description": "Invite a colleague to collaborate on your policy portfolio.",
        "href": "/app/settings",
    },
]


def _accessible_org(user: CurrentUser) -> uuid.UUID | None:
    """Return the single-org filter for Owner/Viewer; None for Admin/Manager/SuperAdmin."""
    if user.is_super_admin or is_group_wide(user.role):
        return None
    return uuid.UUID(user.org_id) if user.org_id else None


async def get_status(db: AsyncSession, user: CurrentUser) -> OnboardingStatus:
    """Compute the first-run checklist for *user*'s tenant.

    Each step is evaluated with a single COUNT query (no full scans).
    Org scoping mirrors policy_service: Admin/Manager see the whole group;
    Owner/Viewer are filtered to their own org (for models that carry org_id).
    """
    if not user.tenant_id:
        # No tenant yet — all steps incomplete.
        steps = [
            OnboardingStep(done=False, **{k: v for k, v in s.items()})
            for s in _STEPS
        ]
        return OnboardingStatus(
            steps=steps,
            complete=False,
            completed_count=0,
            total=len(_STEPS),
        )

    tid = uuid.UUID(user.tenant_id)
    org = _accessible_org(user)

    # ------------------------------------------------------------------
    # 1. providers — tenant-scoped only (no org_id on Provider)
    # ------------------------------------------------------------------
    prov_stmt = select(func.count()).select_from(Provider).where(
        Provider.tenant_id == tid
    )
    provider_count: int = (await db.execute(prov_stmt)).scalar_one()

    # ------------------------------------------------------------------
    # 2. policies — tenant + org-scoped
    # ------------------------------------------------------------------
    pol_stmt = select(func.count()).select_from(Policy).where(
        Policy.tenant_id == tid
    )
    if org is not None:
        pol_stmt = pol_stmt.where(Policy.org_id == org)
    policy_count: int = (await db.execute(pol_stmt)).scalar_one()

    # ------------------------------------------------------------------
    # 3. policy_documents — tenant + org-scoped
    # ------------------------------------------------------------------
    doc_stmt = select(func.count()).select_from(PolicyDocument).where(
        PolicyDocument.tenant_id == tid
    )
    if org is not None:
        doc_stmt = doc_stmt.where(PolicyDocument.org_id == org)
    document_count: int = (await db.execute(doc_stmt)).scalar_one()

    # ------------------------------------------------------------------
    # 4. alert rules OR alerts — tenant-scoped (AlertRule has no org_id)
    # ------------------------------------------------------------------
    rule_stmt = select(func.count()).select_from(AlertRule).where(
        AlertRule.tenant_id == tid
    )
    rule_count: int = (await db.execute(rule_stmt)).scalar_one()
    if rule_count == 0:
        # Fallback: check if any alert has been generated (org-scoped where applicable)
        alert_stmt = select(func.count()).select_from(Alert).where(
            Alert.tenant_id == tid
        )
        if org is not None:
            alert_stmt = alert_stmt.where(Alert.org_id == org)
        rule_count = (await db.execute(alert_stmt)).scalar_one()

    # ------------------------------------------------------------------
    # 5. profiles > 1 OR any invitation — tenant-scoped
    # ------------------------------------------------------------------
    profile_stmt = select(func.count()).select_from(Profile).where(
        Profile.tenant_id == tid
    )
    profile_count: int = (await db.execute(profile_stmt)).scalar_one()
    team_done = profile_count > 1

    if not team_done:
        inv_stmt = select(func.count()).select_from(Invitation).where(
            Invitation.tenant_id == tid
        )
        inv_count: int = (await db.execute(inv_stmt)).scalar_one()
        team_done = inv_count > 0

    # ------------------------------------------------------------------
    # Assemble steps
    # ------------------------------------------------------------------
    done_flags = {
        "provider": provider_count > 0,
        "policy": policy_count > 0,
        "document": document_count > 0,
        "alert": rule_count > 0,
        "team": team_done,
    }

    steps = [
        OnboardingStep(done=done_flags[s["key"]], **{k: v for k, v in s.items()})
        for s in _STEPS
    ]

    completed_count = sum(1 for s in steps if s.done)
    total = len(steps)
    complete = completed_count == total

    return OnboardingStatus(
        steps=steps,
        complete=complete,
        completed_count=completed_count,
        total=total,
    )
