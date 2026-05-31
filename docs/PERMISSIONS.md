# sVault — Permission Matrix

> Owned by `auth-rbac-engineer`. Read by api-engineer (function-level guards), db-architect (RLS),
> ui-ux-designer (hide/disable actions), notifications-engineer (who receives/escalates), search-engineer (RAG access).
> Seeded from PROJECT_BRIEF roles — refine with the user.

## Privilege planes
- **Platform plane** — `Super Admin` (SaaS owner/staff). Lives ABOVE all tenants. Manages plans/pricing, global config & secrets (AI keys, channel/Razorpay credentials), tenants, platform analytics. Not scoped to any tenant. All actions audit-logged.
- **Tenant plane** — the roles below, scoped to a tenant (corporate group) + org.

## Roles
- **Super Admin** (platform) — manage subscription plans, global env/secrets/AI keys, all tenants (suspend/activate/impersonate), platform analytics. NOT a tenant role.
- **Admin** — full access within the tenant; manage users, roles, providers, categories, tenant integrations/channel credentials, org tree, subscription/billing, settings.
- **Manager** — view all policies + dashboard; create/edit any policy; configure alerts; run reports. No system/integration settings.
- **Owner** (team member) — manage the policies they own (the person who finalized the vendor); receives alerts for their policies.
- **Viewer** — read-only dashboard + records; no edits.

## Matrix (resource × action × role)
| Resource | Action | Admin | Manager | Owner | Viewer |
|----------|--------|:-----:|:-------:|:-----:|:------:|
| Policy | create | ✅ | ✅ | ✅ | ❌ |
| Policy | read   | ✅ | ✅ | own + shared | ✅ (read-only) |
| Policy | update | ✅ | ✅ | own only | ❌ |
| Policy | delete/archive | ✅ | ✅ | ❌ | ❌ |
| Document | upload/read | ✅ | ✅ | own policies | read-only |
| Document | delete | ✅ | ✅ | ❌ | ❌ |
| Alert config | edit | ✅ | ✅ | own policies | ❌ |
| Provider/Vendor | manage | ✅ | ✅ | ❌ | read |
| User & roles | manage | ✅ | ❌ | ❌ | ❌ |
| Integrations/credentials | manage | ✅ | ❌ | ❌ | ❌ |
| Reports/analytics | view | ✅ | ✅ | own scope | ✅ |
| Audit log | view | ✅ | ❌ | ❌ | ❌ |
| Ask sVault (RAG) | query | ✅ | ✅ | own + shared docs | own + shared docs |
| Subsidiary / org tree | manage | ✅ (group) | ❌ | ❌ | ❌ |
| Subsidiary data | view | parent-admin: all subs | own org | own org | own org |
| Subscription / plan | manage & upgrade | ✅ (group billing) | ❌ | ❌ | ❌ |
| Approval request | submit | ✅ | ✅ | ✅ | ❌ |
| Approval request | approve/reject | ✅ | ✅ | ❌ | ❌ |
| Self-approval (`approve:self`) | own request | ✅ | ✅ | ❌ | ❌ |
| API keys (third-party) | issue/revoke | ✅ (if plan allows) | ❌ | ❌ | ❌ |

## Platform-plane permissions (Super Admin only — above all tenants)
| Capability | Super Admin |
|------------|:-----------:|
| Subscription **plans & pricing** (create/edit tiers, limits, entitlement map) | ✅ |
| Global **env / secrets / AI API keys** (Claude, WhatsApp, SMS, Razorpay, email) | ✅ (encrypted, audit-logged) |
| **Tenant** management (list/suspend/activate/impersonate) | ✅ |
| Platform **analytics** (MRR, conversions, usage) | ✅ |
| Coupons, announcements | ✅ |
> No tenant-plane role can access any platform-plane capability.

## Enforcement (3 layers — defense in depth)
- **Function level** (FastAPI dep `require_permission`): can this role call this endpoint?
- **Object level** (service-layer check): can this user act on *this* row? (Owner = only own policies.)
- **Database** (RLS): mirror of the above; RAG/vector search filtered by the same rules.

### Object-level owner scoping (BOLA defence) — implementation
The **owner** role may only see/act on policies where `policies.owner_id == their user id`,
for reads AND writes AND everything derived from policies. Admin / Manager / Viewer /
Super-Admin have **no object restriction** (org/group scope only). Tenant + org scoping is
applied *in addition*, never replaced.

Centralised helper: `policy_service._owner_filter(user)` → returns the user's UUID for the
`owner` role, else `None` (Super-Admin always `None`). Applied alongside
`_accessible_org_filter` at **every** read/aggregation touching `policies`:

| Site | How the owner filter is applied |
|------|--------------------------------|
| `policy_service.list_policies` | `WHERE policies.owner_id = :uid` |
| `policy_service.get_policy` | `WHERE policies.owner_id = :uid` → non-owned ⇒ `None` ⇒ 404 (no existence leak) |
| `policy_service.update/delete/renew/mark_renewed` | inherit via `get_policy` (+ existing defence-in-depth check in `update_policy`) |
| documents / installments / alert-rule sub-resources | inherit via `get_policy` |
| `dashboard_service.get_dashboard` (all aggregates) | owner filter inside `_scoped()` |
| `dashboard_service.get_group_dashboard` | totals via `_scoped()`; per-org rollup `WHERE owner_id` (collapses to own policies) |
| `data_io_service` renewal report + policy export | `WHERE policies.owner_id = :uid` |
| `document_library_service` (list + chunk-resolve join) | join to `policies`, `WHERE policies.owner_id = :uid` |
| `alert_service.list_alerts` | `WHERE alert.policy_id IN (SELECT id FROM policies WHERE owner_id = :uid)` |
| `notification_feed_service` feed + history (alerts only) | same policy-ownership subquery; approvals portion unchanged (org-scoped) |
| `account_export_service` (DPDP) | policies + policy_documents owner-scoped; profiles/providers/installments/approvals stay tenant/org-scoped |

Unchanged (still org-scoped, owners included): **providers**, **approvals** (owners still see
org approvals), tenant settings. Calendar inherits via `list_policies`.
Negative + positive isolation tests: `backend/tests/test_object_level_access.py`.
**RLS mirror (db-architect):** add `policies.owner_id = auth.uid()` for `role = 'owner'` and the
equivalent join/subquery predicates for `policy_documents`, `alerts`, `policy_installments`.

> ⚠️ If multi-tenant (Q1) is chosen, add a `tenant_id` scope to every rule and RLS policy.
