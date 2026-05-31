"""Weekly renewal email digest service.

Sends each tenant's admins/owners a plain-text summary of policies expiring
within the next 30 days.  Designed to be triggered weekly via pg_cron or
Vercel Cron hitting POST /api/v1/digests/dispatch.

Design notes
------------
- All DB queries are tenant-scoped; the dispatch_all variant iterates active
  tenants and fetches each tenant's admins without cross-tenant leakage.
- Email delivery is delegated to the existing email adapter
  (app.services.notifications.email.send).  Simulated mode (no EMAIL_API_KEY)
  logs intent and returns status="simulated" — digest.sent is still True in
  that case so tests / on-demand use do not require live keys.
- Errors for a single recipient are swallowed with a warning log so one bad
  address never aborts the full dispatch run.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.insurance import Policy
from app.db.models.tenancy import Profile, Tenant
from app.services.notifications import email as email_adapter

logger = logging.getLogger(__name__)

# Lead-time window for the digest (policies expiring within this many days).
DIGEST_WINDOW_DAYS = 30

# Roles that receive the digest.
_ADMIN_ROLES = ("admin", "owner")


# ---------------------------------------------------------------------------
# Text builder (pure function — unit-testable without a DB)
# ---------------------------------------------------------------------------

def build_digest_text(policies: list) -> str:
    """Return a plain-text weekly digest body listing policies expiring soon.

    Args:
        policies: sequence of Policy ORM objects (or duck-typed objects with
                  .title, .category, .expiry_date, .premium_inr attributes).
                  Expected to be pre-filtered to the ≤30-day window.

    Returns:
        A branded plain-text string suitable for use as an email body.
    """
    today = date.today()

    # Filter to those that have an expiry date and sort soonest-first.
    upcoming = sorted(
        [p for p in policies if p.expiry_date is not None],
        key=lambda p: p.expiry_date,
    )

    lines: list[str] = [
        "sVault — Weekly Renewal Digest",
        "=" * 40,
        "",
    ]

    if not upcoming:
        lines.append("No upcoming renewals in the next 30 days. All clear!")
        lines.append("")
        lines.append("Log in to sVault to manage your portfolio.")
        return "\n".join(lines)

    lines.append(
        f"You have {len(upcoming)} polic{'y' if len(upcoming) == 1 else 'ies'} "
        f"expiring in the next {DIGEST_WINDOW_DAYS} days:"
    )
    lines.append("")

    for idx, policy in enumerate(upcoming, start=1):
        days_left = (policy.expiry_date - today).days
        premium_str = (
            f"INR {policy.premium_inr:,.2f}"
            if policy.premium_inr is not None
            else "N/A"
        )
        lines.append(
            f"{idx}. {policy.title}"
            f"\n   Category : {policy.category}"
            f"\n   Expiry   : {policy.expiry_date} ({days_left} day(s) left)"
            f"\n   Premium  : {premium_str}"
        )
        lines.append("")

    lines.append("-" * 40)
    lines.append("Log in to sVault to view details and initiate renewals.")
    lines.append("This is an automated digest — do not reply to this email.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-tenant send
# ---------------------------------------------------------------------------

async def send_for_tenant(
    db: AsyncSession,
    tenant_id: str | object,
    recipient_email: str,
) -> dict:
    """Fetch the tenant's soon-expiring policies, build the digest, and email it.

    Args:
        db: async SQLAlchemy session.
        tenant_id: UUID of the tenant (str or uuid.UUID).
        recipient_email: the address to send the digest to.

    Returns:
        ``{"sent": bool, "recipient": str, "policies": int}``
    """
    import uuid as _uuid

    if not isinstance(tenant_id, _uuid.UUID):
        tenant_id = _uuid.UUID(str(tenant_id))

    today = date.today()
    window = today + timedelta(days=DIGEST_WINDOW_DAYS)

    stmt = (
        select(Policy)
        .where(
            Policy.tenant_id == tenant_id,
            Policy.expiry_date.is_not(None),
            Policy.expiry_date >= today,
            Policy.expiry_date <= window,
            Policy.status.in_(("active", "expiring")),
        )
        .order_by(Policy.expiry_date.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()

    body = build_digest_text(rows)
    result = await email_adapter.send(
        recipient_email,
        body,
        template="weekly_digest",
    )

    sent = result.status in ("sent", "simulated")
    logger.info(
        "digest | tenant=%s | recipient=%s | policies=%d | status=%s",
        tenant_id,
        recipient_email,
        len(rows),
        result.status,
    )
    return {"sent": sent, "recipient": recipient_email, "policies": len(rows)}


# ---------------------------------------------------------------------------
# Cross-tenant dispatch (cron)
# ---------------------------------------------------------------------------

async def dispatch_all(db: AsyncSession) -> dict:
    """Iterate all active tenants, resolve admin/owner recipients, and send digests.

    Best-effort: per-recipient errors are logged and swallowed so one bad
    address never aborts the full run.

    Returns:
        ``{"tenants": N, "emails_sent": M}``
    """
    # Resolve all active tenants.
    tenant_rows = (
        await db.execute(
            select(Tenant).where(Tenant.status == "active")
        )
    ).scalars().all()

    tenants_processed = 0
    emails_sent = 0

    for tenant in tenant_rows:
        # Fetch admin/owner profiles that have an email address.
        profile_rows = (
            await db.execute(
                select(Profile).where(
                    Profile.tenant_id == tenant.id,
                    Profile.role.in_(_ADMIN_ROLES),
                    Profile.is_active.is_(True),
                    Profile.email.is_not(None),
                )
            )
        ).scalars().all()

        # Deduplicate by email (a user could theoretically appear twice).
        seen: set[str] = set()
        recipients = []
        for prof in profile_rows:
            if prof.email and prof.email not in seen:
                seen.add(prof.email)
                recipients.append(prof.email)

        if not recipients:
            logger.debug("digest dispatch | tenant=%s | no admin recipients; skipping", tenant.id)
            tenants_processed += 1
            continue

        for recipient_email in recipients:
            try:
                result = await send_for_tenant(db, tenant.id, recipient_email)
                if result["sent"]:
                    emails_sent += 1
            except Exception:  # noqa: BLE001
                logger.warning(
                    "digest dispatch | tenant=%s | recipient=%s | error sending; continuing",
                    tenant.id,
                    recipient_email,
                    exc_info=True,
                )

        tenants_processed += 1

    logger.info(
        "digest dispatch complete | tenants=%d | emails_sent=%d",
        tenants_processed,
        emails_sent,
    )
    return {"tenants": tenants_processed, "emails_sent": emails_sent}
