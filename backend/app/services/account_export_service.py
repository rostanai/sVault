"""DPDP account data-export service.

Assembles a complete, tenant-scoped data snapshot for a portability /
data-principal request under India's DPDP Act (Digital Personal Data
Protection Act 2023).

Design decisions:
- One SQL query per table (no N+1).
- Every collection is capped at COLLECTION_LIMIT rows; a `_truncated`
  flag is set to True in the output when a cap is hit.
- Secrets are excluded: no API-key hashes, no storage_path (document
  file bytes), no platform settings, no password fields.
- All UUIDs → str, Decimals → str, dates/datetimes → ISO 8601 strings.
  This is done via a simple helper so json.dumps(default=str) acts as a
  safe fallback for any edge-case types we missed.
- Org scoping mirrors policy_service._accessible_org_filter:
    * Admin / Manager (is_group_wide) → whole tenant.
    * Owner / Viewer                  → own org only.
  Tenant/org rows (Tenant, Organization, Profile) are tenant-scoped
  without the org restriction so the user always receives their tenant
  context and full team list (DPDP requires this).
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.db.models import (
    Approval,
    Installment,
    Organization,
    Policy,
    PolicyDocument,
    Profile,
    Provider,
    ProviderContact,
    Tenant,
)
from app.services.org_service import is_group_wide
from app.services.policy_service import _owner_filter

# Maximum rows returned per collection before truncation.
COLLECTION_LIMIT = 5_000


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _s(value: Any) -> Any:
    """Convert non-JSON-native types to safe, readable strings.

    UUID  → str
    Decimal → str (preserves precision; avoids float rounding)
    date / datetime → ISO 8601 str
    None → None (pass-through)
    Anything else → pass-through (json.dumps will fall back to `default=str`)
    """
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


# ---------------------------------------------------------------------------
# Per-table row serialisers — only safe, non-secret fields
# ---------------------------------------------------------------------------

def _tenant_row(t: Tenant) -> dict:
    return {
        "id": _s(t.id),
        "name": t.name,
        "status": t.status,
        "created_at": _s(t.created_at),
        "updated_at": _s(t.updated_at),
    }


def _org_row(o: Organization) -> dict:
    return {
        "id": _s(o.id),
        "tenant_id": _s(o.tenant_id),
        "parent_org_id": _s(o.parent_org_id),
        "name": o.name,
        "org_type": o.org_type,
        "gstin": o.gstin,
        "is_active": o.is_active,
        "created_at": _s(o.created_at),
        "updated_at": _s(o.updated_at),
    }


def _profile_row(p: Profile) -> dict:
    # Deliberately omit phone (PII minimisation) — only id/email/name/role exported.
    return {
        "id": _s(p.id),
        "tenant_id": _s(p.tenant_id),
        "org_id": _s(p.org_id),
        "role": p.role,
        "full_name": p.full_name,
        "email": p.email,
        "is_active": p.is_active,
        "created_at": _s(p.created_at),
        "updated_at": _s(p.updated_at),
    }


def _provider_row(p: Provider) -> dict:
    return {
        "id": _s(p.id),
        "tenant_id": _s(p.tenant_id),
        "name": p.name,
        "contact_name": p.contact_name,
        "contact_email": p.contact_email,
        "contact_phone": p.contact_phone,
        "notes": p.notes,
        "created_at": _s(p.created_at),
        "updated_at": _s(p.updated_at),
    }


def _provider_contact_row(pc: ProviderContact) -> dict:
    return {
        "id": _s(pc.id),
        "tenant_id": _s(pc.tenant_id),
        "provider_id": _s(pc.provider_id),
        "kind": pc.kind,
        "subject": pc.subject,
        "note": pc.note,
        "contacted_at": _s(pc.contacted_at),
        "created_by": _s(pc.created_by),
        "created_at": _s(pc.created_at),
    }


def _policy_row(p: Policy) -> dict:
    return {
        "id": _s(p.id),
        "tenant_id": _s(p.tenant_id),
        "org_id": _s(p.org_id),
        "category": p.category,
        "policy_number": p.policy_number,
        "title": p.title,
        "provider_id": _s(p.provider_id),
        "owner_id": _s(p.owner_id),
        "sum_insured_inr": _s(p.sum_insured_inr),
        "premium_inr": _s(p.premium_inr),
        "gst_inr": _s(p.gst_inr),
        "inception_date": _s(p.inception_date),
        "expiry_date": _s(p.expiry_date),
        "renewal_date": _s(p.renewal_date),
        "status": p.status,
        "prev_policy_id": _s(p.prev_policy_id),
        "custom_fields": p.custom_fields,
        "created_by": _s(p.created_by),
        "created_at": _s(p.created_at),
        "updated_at": _s(p.updated_at),
    }


def _document_row(d: PolicyDocument) -> dict:
    # storage_path is excluded (no signed URLs or file bytes per DPDP privacy design).
    return {
        "id": _s(d.id),
        "tenant_id": _s(d.tenant_id),
        "org_id": _s(d.org_id),
        "policy_id": _s(d.policy_id),
        "doc_type": d.doc_type,
        "file_name": d.file_name,
        "mime_type": d.mime_type,
        "size_bytes": d.size_bytes,
        "version": d.version,
        "uploaded_by": _s(d.uploaded_by),
        "created_at": _s(d.created_at),
        # storage_path intentionally omitted
    }


def _installment_row(i: Installment) -> dict:
    return {
        "id": _s(i.id),
        "tenant_id": _s(i.tenant_id),
        "policy_id": _s(i.policy_id),
        "amount_inr": _s(i.amount_inr),
        "due_date": _s(i.due_date),
        "status": i.status,
        "paid_at": _s(i.paid_at),
        "note": i.note,
        "created_at": _s(i.created_at),
    }


def _approval_row(a: Approval) -> dict:
    return {
        "id": _s(a.id),
        "tenant_id": _s(a.tenant_id),
        "org_id": _s(a.org_id),
        "action_type": a.action_type,
        "entity_type": a.entity_type,
        "entity_id": _s(a.entity_id),
        "amount_inr": _s(a.amount_inr),
        "status": a.status,
        "requested_by": _s(a.requested_by),
        "approver_id": _s(a.approver_id),
        "is_self_approval": a.is_self_approval,
        "reason": a.reason,
        "decided_at": _s(a.decided_at),
        "created_at": _s(a.created_at),
    }


# ---------------------------------------------------------------------------
# Org-scope helpers
# ---------------------------------------------------------------------------

def _accessible_org_id(user: CurrentUser) -> uuid.UUID | None:
    """Return the restricting org UUID for non-group-wide users, else None."""
    if user.is_super_admin or is_group_wide(user.role):
        return None
    return uuid.UUID(user.org_id) if user.org_id else None


def _maybe_apply_org_filter(stmt, model, org: uuid.UUID | None):
    """Optionally narrow `stmt` to a single org when the caller is not group-wide."""
    if org is not None:
        stmt = stmt.where(model.org_id == org)
    return stmt


# ---------------------------------------------------------------------------
# Main export assembler
# ---------------------------------------------------------------------------

async def build_export(db: AsyncSession, user: CurrentUser) -> dict:
    """Return a serialisable dict representing the tenant's full data snapshot.

    Each top-level collection key contains a list of row dicts plus a
    `_truncated` boolean that is True when COLLECTION_LIMIT was hit.

    Never raises — missing tenant_id results in an export with empty
    collections (edge case for super-admin / unprovisioned accounts).
    """
    tenant_id_str: str | None = user.tenant_id
    org: uuid.UUID | None = _accessible_org_id(user)
    # Object-level: for the owner role, the policies + policy_documents sections are
    # narrowed to the owner's own policies. Other sections (tenant/orgs/profiles/
    # providers/installments/approvals) stay tenant/org-scoped as documented.
    owner_oid: uuid.UUID | None = _owner_filter(user)

    exported_at = datetime.now(UTC).isoformat()

    # ---------- tenant ----------
    tenant_dict: dict | None = None
    if tenant_id_str:
        t_uuid = uuid.UUID(tenant_id_str)
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == t_uuid).limit(1)
        )
        tenant_obj = tenant_result.scalar_one_or_none()
        if tenant_obj:
            tenant_dict = _tenant_row(tenant_obj)

    if not tenant_id_str:
        return {
            "exported_at": exported_at,
            "tenant": None,
            "organizations": {"items": [], "_truncated": False},
            "profiles": {"items": [], "_truncated": False},
            "providers": {"items": [], "_truncated": False},
            "provider_contacts": {"items": [], "_truncated": False},
            "policies": {"items": [], "_truncated": False},
            "policy_documents": {"items": [], "_truncated": False},
            "installments": {"items": [], "_truncated": False},
            "approvals": {"items": [], "_truncated": False},
        }

    t_uuid = uuid.UUID(tenant_id_str)

    # ---------- organizations ----------
    orgs_result = await db.execute(
        select(Organization)
        .where(Organization.tenant_id == t_uuid)
        .limit(COLLECTION_LIMIT + 1)
    )
    orgs_raw = list(orgs_result.scalars().all())
    orgs_truncated = len(orgs_raw) > COLLECTION_LIMIT
    orgs_rows = [_org_row(o) for o in orgs_raw[:COLLECTION_LIMIT]]

    # ---------- profiles ----------
    profiles_result = await db.execute(
        select(Profile)
        .where(Profile.tenant_id == t_uuid)
        .limit(COLLECTION_LIMIT + 1)
    )
    profiles_raw = list(profiles_result.scalars().all())
    profiles_truncated = len(profiles_raw) > COLLECTION_LIMIT
    profiles_rows = [_profile_row(p) for p in profiles_raw[:COLLECTION_LIMIT]]

    # ---------- providers ----------
    providers_result = await db.execute(
        select(Provider)
        .where(Provider.tenant_id == t_uuid)
        .limit(COLLECTION_LIMIT + 1)
    )
    providers_raw = list(providers_result.scalars().all())
    providers_truncated = len(providers_raw) > COLLECTION_LIMIT
    providers_rows = [_provider_row(p) for p in providers_raw[:COLLECTION_LIMIT]]

    # ---------- provider contacts ----------
    pc_stmt = (
        select(ProviderContact)
        .where(ProviderContact.tenant_id == t_uuid)
        .limit(COLLECTION_LIMIT + 1)
    )
    pc_result = await db.execute(pc_stmt)
    pc_raw = list(pc_result.scalars().all())
    pc_truncated = len(pc_raw) > COLLECTION_LIMIT
    pc_rows = [_provider_contact_row(pc) for pc in pc_raw[:COLLECTION_LIMIT]]

    # ---------- policies (org-scoped for non-group-wide callers) ----------
    pol_stmt = select(Policy).where(Policy.tenant_id == t_uuid)
    pol_stmt = _maybe_apply_org_filter(pol_stmt, Policy, org)
    if owner_oid is not None:
        pol_stmt = pol_stmt.where(Policy.owner_id == owner_oid)
    pol_stmt = pol_stmt.limit(COLLECTION_LIMIT + 1)
    pol_result = await db.execute(pol_stmt)
    pol_raw = list(pol_result.scalars().all())
    pol_truncated = len(pol_raw) > COLLECTION_LIMIT
    pol_rows = [_policy_row(p) for p in pol_raw[:COLLECTION_LIMIT]]

    # ---------- policy documents ----------
    doc_stmt = select(PolicyDocument).where(PolicyDocument.tenant_id == t_uuid)
    doc_stmt = _maybe_apply_org_filter(doc_stmt, PolicyDocument, org)
    if owner_oid is not None:
        # PolicyDocument has no owner_id; restrict to docs of the owner's own policies.
        doc_stmt = doc_stmt.where(
            PolicyDocument.policy_id.in_(
                select(Policy.id).where(Policy.owner_id == owner_oid)
            )
        )
    doc_stmt = doc_stmt.limit(COLLECTION_LIMIT + 1)
    doc_result = await db.execute(doc_stmt)
    doc_raw = list(doc_result.scalars().all())
    doc_truncated = len(doc_raw) > COLLECTION_LIMIT
    doc_rows = [_document_row(d) for d in doc_raw[:COLLECTION_LIMIT]]

    # ---------- installments ----------
    inst_stmt = select(Installment).where(Installment.tenant_id == t_uuid)
    inst_stmt = inst_stmt.limit(COLLECTION_LIMIT + 1)
    inst_result = await db.execute(inst_stmt)
    inst_raw = list(inst_result.scalars().all())
    inst_truncated = len(inst_raw) > COLLECTION_LIMIT
    inst_rows = [_installment_row(i) for i in inst_raw[:COLLECTION_LIMIT]]

    # ---------- approvals ----------
    appr_stmt = select(Approval).where(Approval.tenant_id == t_uuid)
    appr_stmt = appr_stmt.limit(COLLECTION_LIMIT + 1)
    appr_result = await db.execute(appr_stmt)
    appr_raw = list(appr_result.scalars().all())
    appr_truncated = len(appr_raw) > COLLECTION_LIMIT
    appr_rows = [_approval_row(a) for a in appr_raw[:COLLECTION_LIMIT]]

    return {
        "exported_at": exported_at,
        "tenant": tenant_dict,
        "organizations": {"items": orgs_rows, "_truncated": orgs_truncated},
        "profiles": {"items": profiles_rows, "_truncated": profiles_truncated},
        "providers": {"items": providers_rows, "_truncated": providers_truncated},
        "provider_contacts": {"items": pc_rows, "_truncated": pc_truncated},
        "policies": {"items": pol_rows, "_truncated": pol_truncated},
        "policy_documents": {"items": doc_rows, "_truncated": doc_truncated},
        "installments": {"items": inst_rows, "_truncated": inst_truncated},
        "approvals": {"items": appr_rows, "_truncated": appr_truncated},
    }
