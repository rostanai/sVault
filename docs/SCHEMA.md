# sVault — Database Schema (Supabase Postgres)

> Migrations in `supabase/migrations/` (apply via Supabase MCP `apply_migration` after auth).
> Project ref `hgopttbpoyvmlzgzyzio`. Covers every object type below.

## Extensions
`pgcrypto` (uuid/digest) · `pg_trgm` (fuzzy search) · `unaccent` · **`vector`** (pgvector RAG) · `btree_gin` · **`pg_cron`** (serverless scheduler).

## Enumerated Types
`policy_category`, `policy_status`, `org_type`, `tenant_role`, `alert_channel`, `alert_status`, `plan_tier`, `subscription_status`, `approval_status`, `approval_action`, `document_type`, `audit_action`.

## Tables (21)
**Platform plane:** `plans`, `platform_settings` (encrypted secrets), `platform_audit_log`.
**Tenancy & org:** `tenants`, `organizations` (parent/subsidiary tree), `profiles`, `invitations`.
**Billing:** `subscriptions`, `invoices`, `billing_events` (Razorpay webhooks), `api_keys`, `webhooks`.
**Insurance:** `providers`, `policies`, `policy_documents`.
**Alerts:** `alert_rules`, `alerts`, `notification_log`.
**Workflow/compliance:** `approvals`, `audit_log`.
**RAG:** `document_chunks` (pgvector embeddings).

## Functions
`jwt_tenant_id()`, `jwt_org_id()`, `jwt_role()`, `is_super_admin()` (read verified JWT claims) ·
`descendant_org_ids(uuid)` + `accessible_org_ids()` (parent roll-up) ·
`set_updated_at()`, `handle_new_user()`, `compute_policy_status()`, `audit_row()` ·
`match_document_chunks()` (RLS-aware vector search).

## Triggers
`updated_at` on 8 tables · `handle_new_user` on `auth.users` · `compute_policy_status` on `policies` (auto active/expiring/lapsed) · `audit_row` on `policies`, `policy_documents`, `approvals`, `subscriptions`, `api_keys`.

## Indexes
tenant_id/org_id on every table (RLS columns) · policy expiry/status/owner/provider/category · alert schedule · `pg_trgm` GIN on policy title/number · **HNSW** vector index on `document_chunks.embedding` · api-key hash · billing event id.

## Publications (Realtime)
`supabase_realtime` includes `policies`, `alerts`, `approvals`, `notification_log` (RLS-enforced per subscriber) for live dashboard/approval updates.

## RLS model (two planes)
- **Platform plane** (`plans`, `platform_settings`, `platform_audit_log`) → **Super Admin only** (plans also read-only to all for the pricing page).
- **Tenant plane** → scoped by `tenant_id` + **`accessible_org_ids()`** (parent admins roll up across subsidiaries; owners/viewers see their own org). Viewers read-only; service role (FastAPI/Razorpay) bypasses for trusted writes.

## Apply order
0001 extensions/enums/helpers → 0002 platform/tenancy → 0003 billing → 0004 insurance → 0005 alerts/approvals/audit/rag → 0006 functions/triggers → 0007 indexes → 0008 RLS → 0009 publications.
