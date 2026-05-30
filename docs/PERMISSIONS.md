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

> ⚠️ If multi-tenant (Q1) is chosen, add a `tenant_id` scope to every rule and RLS policy.
