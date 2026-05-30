# sVault — Handoff Log (append-only)

> Every agent appends an entry when it finishes a task. The tech-lead reads this to sequence work.
> Newest entries at the bottom.

### 2026-05-30 — tech-lead — team bootstrap
- Did: created the 9-agent team in `.claude/agents/`, the stack baseline (`docs/STACK.md`), and the coordination protocol (`docs/TEAM.md`).
- Ready for: the user to fill `docs/PROJECT_BRIEF.md` (what sVault is + roles), then `project-setup` to scaffold the repo.
- Contract updated: STACK.md, TEAM.md, PROJECT_BRIEF.md (placeholder).
- Open questions: What is sVault? Confirm stack = FastAPI + Supabase + Next.js.

### 2026-05-30 — tech-lead — product defined + research + full sync (no-gap update)
- Did: Defined the product (Corporate Insurance Portfolio & Renewal Mgmt System) in PROJECT_BRIEF.md.
  Ran verified deep research → `docs/RESEARCH.md` (competitors: TrustLayer/Certificial/Insuraa/InsureBook/Remindax/ExpiryEdge — none target own-portfolio = real gap; India DLT + DPDP Rules 2025 facts).
  Produced full feature catalog → `docs/FEATURES.md` (🟢MVP/🟡P1/🔵P2). Removed e-signature.
  Added AI/RAG ("Ask sVault") research → FEATURES §9A + folded into search-engineer.
  **Created new agent `notifications-engineer`** to own the renewal-alert engine (was an ownership gap).
  Wrote `docs/DECISIONS.md` (D1–D8 locked, Q1–Q7 open, A1–A4 default assumptions).
  Filled `docs/PERMISSIONS.md` with Admin/Manager/Owner/Viewer matrix.
  Put 6 non-negotiable domain constraints (DLT, WhatsApp utility, DPDP, permission-aware RAG, alert cadence, INR/GST) into TEAM.md so all agents inherit them. Updated CLAUDE.md doc map + roster.
- Ready for: user to resolve open questions Q1 (single vs multi-tenant), Q4/Q5 (MVP scope), then `project-setup` to scaffold. Agents register on next Claude Code restart.
- Contract updated: PROJECT_BRIEF, RESEARCH, FEATURES, DECISIONS, PERMISSIONS, TEAM, CLAUDE.md; new agent notifications-engineer.
- Open questions / decisions needed: Q1–Q7 in DECISIONS.md (esp. tenancy + MVP AI scope).

### 2026-05-30 — tech-lead — SaaS monetization added (subscriptions, payments, trial, onboarding)
- Did: Researched + added SaaS subscription/plans, feature-gating/entitlements, Razorpay payments, 14-day trial, Google OAuth, and onboarding/registration → FEATURES.md §16–18 (incl. draft plan→feature map).
  **Created new agent `billing-engineer`** (Razorpay + entitlements). Updated `auth-rbac-engineer` for Google OAuth + multi-tenant. Resolved Q1 → **multi-tenant SaaS** (D9). Added D9–D12 + constraints #7 (multi-tenant) and #8 (server-side gating) to TEAM.md so all agents inherit. Updated DECISIONS (new Q6/Q8/Q9, assumptions A1/A5/A6), CLAUDE.md, roster → **11 agents**.
- Ready for: user to confirm plan pricing (Q6), free-tier vs hard-paywall (Q8), tenant-isolation model (Q9, default shared-schema+RLS), then build.
- Contract updated: FEATURES, DECISIONS, TEAM, PERMISSIONS(impl), CLAUDE.md; new agent billing-engineer; auth-rbac updated.
- Open questions / decisions needed: Q2–Q9 in DECISIONS.md.

### 2026-05-30 — tech-lead — org hierarchy + approvals + high-scale + in-app upgrade
- Did: Captured user's new requirements. **NEW**: parent↔subsidiary **org hierarchy** (FEATURES §19), **approval workflows** with self-approval + role/permission routing (§20); promoted **in-app subscription/upgrade page** (Razorpay, anytime from trial) to MVP (§16). Confirmed **high scale** (D13), channel priority **WhatsApp+Email+SMS** (D14, resolves Q3), approvals in scope (D15, resolves Q4). Added D13–D17, A7–A9, open Q10–Q12. Added TEAM constraints #9 (org hierarchy), #10 (approvals), #11 (high scale) → all agents inherit. Updated agents: db-architect (org tree + scale + approvals tables), auth-rbac (hierarchy scoping + approval/self-approval perms), api-engineer (org scope + approval endpoints + scale), billing-engineer (in-app upgrade + group billing), ui-ux-designer (subscription/approval/org-switcher screens). Updated PROJECT_BRIEF, PERMISSIONS, CLAUDE.md.
- Ready for: user to answer Q10 (group vs per-subsidiary billing), Q11 (which actions need approval + thresholds), Q12 (who self-approves), Q6 (pricing). Then build.
- Contract updated: FEATURES, DECISIONS, TEAM, PERMISSIONS, PROJECT_BRIEF, CLAUDE.md; agents db/auth/api/billing/ui.
- Open questions / decisions needed: Q5–Q12 in DECISIONS.md.

### 2026-05-30 — notifications/api — M4 renewal alert engine (PR #3)
- Did: Built the alert engine on branch m4-alerts (PR #3, base m2-policies). Models AlertRule/Alert/NotificationLog; `alert_engine.py` (IST-correct due-day math, rule resolution per-policy→tenant→default 60/30/15/7/1 + whatsapp/email, idempotent scan_and_dispatch via unique policy/lead_day/channel, acknowledge); `notifier.py` (pluggable channels, simulated mode until creds); endpoints GET|PUT /policies/{id}/alert-rule, GET /alerts, POST /alerts/{id}/ack, POST /alerts/dispatch (cron-secret guarded → 404 without). pg_cron activation documented in DEPLOYMENT.md. 48 tests green, ruff clean.
- Pending: real channel senders (WhatsApp BSP/SMS DLT — START_NOW), activate pg_cron after backend deploy, live integration test (needs DATABASE_URL).

### 2026-05-30 — db/api/devops — DB LIVE + M2 policies + isolation PROVEN
- Did: Authenticated Supabase (plugin MCP). Applied all migrations 0001-0010 to project hgopttbpoyvmlzgzyzio — **21 tables, RLS on all**, enums/functions/triggers/indexes (HNSW+trgm)/realtime publication. Security advisor 18→4 WARN (only low-risk extension_in_public left). Added **Vercel MCP** + `docs/DEPLOYMENT.md` (two-project GitHub auto-deploy). Built **M2 policy/provider CRUD** (models, service with tenant/org scoping + ownership, endpoints) → branch m2-policies, **PR #2** (base m1-auth-org), 34 tests green.
- **VERIFIED (M1/M2 gate):** ran live RLS test — a Tenant-A admin sees only Tenant-A's policy, not Tenant-B's (cross-tenant isolation confirmed at the DB layer; test rolled back).
- Open: Vercel MCP auth (restart + /mcp), set DATABASE_URL in CI for live integration tests, M2 document upload (Storage).

### 2026-05-30 — auth-rbac/api — M1 part 1: auth & authz foundation (code, pushed)
- Did: On branch `m1-auth-org` — `core/security.py` (Supabase JWT verify + claim extraction from app_metadata, CurrentUser), `core/authz.py` (Role enum, permission matrix mirroring PERMISSIONS.md, has_permission, require_permission/require_super_admin deps, super-admin bypass, 404-not-403). 19 unit tests green, ruff clean. Pushed `m0-foundation` + `m1-auth-org` to origin.
- BLOCKED: (1) GitHub `main` not seeded (empty repo → no PR base); need user decision. (2) DB-dependent M1 (SQLAlchemy models, async session via pooler, signup→tenant/org creation, RLS integration + isolation tests) needs Supabase MCP auth (`claude /mcp`).
- Next (M1 part 2 once DB live): models, async session, auth/signup/invite endpoints, org context, RLS isolation tests.

### 2026-05-30 — project-setup/api/devops — M0 foundation scaffold (DONE, code)
- Did: Scaffolded the monorepo and committed to branch `m0-foundation` (74 files).
  **backend/**: FastAPI app factory, /health + /ready, config (pydantic-settings), structured JSON logging,
  error envelope + ErrorCode taxonomy + global handlers + request-id middleware (per ERROR_HANDLING.md),
  Vercel ASGI entrypoint (`api/index.py` + `vercel.json`), pyproject (3.12+, ruff, pytest). **Tests 3/3 green, ruff clean.**
  **frontend/**: Next.js 16 App Router skeleton (React 19, Tailwind v4 OKLCH), error.tsx + not-found.tsx boundaries,
  typed API client mapping the error envelope. **root**: .gitignore, README, GitHub Actions CI (backend ruff+pytest, frontend typecheck+build).
- Verified locally: backend boots, pytest passes, ruff passes.
- BLOCKED on user (external): (1) authenticate Supabase MCP (`claude /mcp`) → apply migrations 0001-0009;
  (2) create Vercel projects + connect GitHub repo for auto-deploy; (3) push branch + open PR (awaiting user go-ahead to push).
- Ready for: M1 (auth/org/RBAC) once DB is migrated. Restart Claude Code so the 12 agents register.
- Contract updated: code under backend/ frontend/ .github/; README.

### 2026-05-30 — tech-lead — PRD + Build Plan
- Did: Wrote `docs/PRD.md` (overview, goals/metrics, personas, scope, FR by epic with phase tags, NFRs, architecture, release phases, acceptance) and `docs/BUILD_PLAN.md` (milestones M0–M9, epics, agent owners, gates, dependency chain). MVP = M0 foundation → M1 auth/org/RBAC → M2 policies/docs → M3 dashboard → M4 alert engine (WhatsApp+Email) → M5 billing/trial/super-admin → M6 approvals+marketing+hardening → ship. Phase 1 = SMS/Telegram, AI RAG, search, group dashboards, dev API, OCR, onboarding. Linked in CLAUDE + TEAM doc map.
- Ready for: user sign-off on plan; resolve Q5/Q6/Q10–Q12; authenticate Supabase MCP + restart → start M0.
- Contract updated: PRD.md, BUILD_PLAN.md (new), CLAUDE, TEAM.

### 2026-05-30 — billing-engineer — M5 billing backend slice (branch m5-billing)

- Did: Built the full M5 billing backend. 81 tests green, ruff clean.
  - **ORM models** (`app/db/models/billing.py`): `Plan`, expanded `Subscription` (added
    current_period_start/end, cancel_at_period_end, razorpay_customer_id/subscription_id),
    `Invoice`, `BillingEvent`, `PlatformSetting`. All enums `create_type=False`.
  - **Config** (`app/core/config.py`): added `razorpay_key_id`, `razorpay_key_secret`,
    `razorpay_webhook_secret`, `secrets_encryption_key`.
  - **Secrets store** (`app/core/secrets_store.py`): Fernet encrypt/decrypt/mask;
    raises `internal_error` if key unconfigured; never stores plaintext.
  - **Razorpay client** (`app/core/razorpay.py`): `create_plan`, `create_subscription`,
    `fetch_subscription` (httpx Basic auth, 10s timeout, `upstream_error` on failure);
    `verify_webhook_signature` — pure HMAC-SHA256 function, unit-testable.
  - **Entitlements** (`app/services/entitlements.py`): `feature_allowed` + `within_limit`
    (pure, no DB); `get_entitlements` / `has_feature` / `check_limit` (DB-backed);
    `require_entitlement(feature)` FastAPI dep factory (403 entitlement_required);
    Free + Pro defaults; -1 = unlimited; trialing → Pro, cancelled/expired → Free.
  - **Subscription service** (`app/services/subscription_service.py`): `get_current`,
    `list_active_plans`, `start_or_update_subscription`, `handle_webhook` (idempotent
    via `billing_events.event_id` unique constraint + IntegrityError race guard).
  - **Platform service** (`app/services/platform_service.py`): plans CRUD; settings
    get/set (encrypt on write, mask on read); tenant list/suspend/activate.
  - **Schemas** (`app/schemas/billing.py`): PlanRead/Create/Update, SubscriptionRead,
    SubscriptionWithEntitlements, SubscribeRequest/Response, SettingRead/Write, TenantRead.
  - **Billing endpoints** (`app/api/v1/billing.py`): GET /plans, GET /billing/subscription,
    POST /billing/subscribe, POST /billing/webhook. Webhook uses `_sig_check` dep
    (no DB dep) that raises AppError(400) on bad signature before get_db is reached.
  - **Platform endpoints** (`app/api/v1/platform.py`): GET/POST/PATCH /platform/plans,
    GET/PUT /platform/settings/{key}, GET /platform/tenants,
    POST /platform/tenants/{id}/suspend|activate. All guarded by `require_super_admin`
    (returns 404 to non-super-admins — platform route invisibility).
  - **Router** (`app/api/v1/router.py`): registered billing + platform routers.
  - **Tests** (`tests/test_m5_billing.py`): 31 tests — feature_allowed/within_limit
    pure logic (free vs pro), webhook sig verification (valid/tampered/wrong/unconfigured),
    secrets_store round-trip + ciphertext-not-plaintext, require_super_admin 404 behavior,
    endpoint 401 guards (billing + platform), webhook 400 without/with-bad-sig, ORM smoke.
  - **Plan map** (`docs/PLANS.md`): full feature + limit matrix, entitlement JSON shape,
    lifecycle transitions, enforcement reference.
  - `cryptography>=42.0` added explicitly to `pyproject.toml` deps.
- Stubs / assumptions:
  - Razorpay keys absent → `create_subscription` skipped (local record still persisted);
    plan's `razorpay_plan_id` must be set by Super Admin for live Razorpay flow.
  - INR prices + exact limits are TBD (DECISIONS Q6 open); Super Admin sets them via
    platform console.
  - `billing_period` stored as text ("monthly"/"annual"); Razorpay interval maps 1:1.
  - Trial→paid conversion via POST /billing/subscribe with a paid plan_id.
  - Dunning emails (failed payment) coordinated with notifications-engineer (not built here).
  - Analytics entitlement stored as bool; basic/full distinction is a frontend concern.
- Pending / next:
  - notifications-engineer: send T-3/T-1/expiry trial reminders + payment failure dunning.
  - api-engineer: protect gated endpoints with `require_entitlement` / `check_limit` calls.
  - devops: set RAZORPAY_KEY_ID/SECRET/WEBHOOK_SECRET + SECRETS_ENCRYPTION_KEY in Vercel env.
  - Super Admin console UI (ui-ux-designer): plan CRUD + settings forms.

### 2026-05-30 — tech-lead — error-handling & debugging standard
- Did: Wrote `docs/ERROR_HANDLING.md` — backend error envelope + code taxonomy + request_id tracing + global handlers, **404-not-403 cross-tenant**, external-service resilience (timeouts/retries/circuit-breakers/idempotency/dead-letter for Razorpay/WhatsApp/SMS/Claude), frontend error boundaries + envelope→friendly UX, debugging/observability (structured logs, Sentry, replay). Added TEAM constraint #18; updated api-engineer + ui-ux-designer agents; CONSIDERATIONS A7b; CLAUDE doc map.
- Contract updated: ERROR_HANDLING.md (new), TEAM, CONSIDERATIONS, CLAUDE; agents api/ui.

### 2026-05-30 — tech-lead — QA agent + start-now checklist
- Did: Created **`qa-test-engineer`** agent (12th) — owns unit/integration/E2E/load tests, esp. **multi-tenant/org isolation** + authz + entitlement + alert-idempotency + RAG-permission tests; merge gate with security-auditor. Added **observability/reliability** ownership to devops-engineer (Sentry, uptime, status page, PITR backups, cost monitoring, pooler, WAF, secrets rotation). Wrote **`docs/START_NOW.md`** — 17-item long-lead checklist (WhatsApp BSP, SMS DLT, Razorpay KYC, legal pages, DPDP grievance officer, DPAs, Google OAuth, Supabase/Vercel/Anthropic setup, email domain, observability, brand). Updated roster → 12 agents, CLAUDE, TEAM.
- Ready for: user to start the 🔴 long-lead items (WhatsApp/SMS/DPAs = today) + finalize pricing; then build.
- Contract updated: new agent qa-test-engineer; START_NOW.md, CONSIDERATIONS owners; devops agent; TEAM, CLAUDE.

### 2026-05-30 — tech-lead — gap analysis (CONSIDERATIONS.md)
- Did: Full gap/risk review → `docs/CONSIDERATIONS.md` (categories A–F, ~40 items, priority-tagged). Surfaced go-live blockers: timezone math, Supabase serverless connection pooling, backups/PITR, observability, PII→LLM data residency, sub-processor DPAs, DPDP grievance officer + data-principal rights, WhatsApp BSP + SMS DLT lead times, pricing. Added TEAM constraints #14–17 (timezone, pooler, PII→LLM, file uploads) so all agents inherit; linked CONSIDERATIONS in doc map. Proposed adding a **qa-test-engineer** agent + observability ownership.
- Ready for: user to review gaps; decide whether to add QA/observability agents; kick off BSP/DLT registration early (long lead time).
- Contract updated: CONSIDERATIONS.md (new), TEAM.
- Open questions: add QA agent? start WhatsApp BSP + SMS DLT now? confirm pricing (Q6/Q8).

### 2026-05-30 — ui-ux-designer/tech-lead — marketing website spec
- Did: Researched modern 2026 B2B SaaS site best practices; authored `docs/MARKETING.md` (full site map: home, features+detail pages, pricing, solutions, comparisons, security, blog/SEO hub, about, contact/demo, legal pages required for Razorpay, app entry points; landing sections; conversion+SEO standards). Added FEATURES §23. Updated ui-ux-designer agent to own the marketing site. D23 locked. Updated TEAM doc map + CLAUDE.
- Ready for: ui-ux-designer to design landing + pricing in Stitch once build starts.
- Contract updated: MARKETING.md, FEATURES, DECISIONS, TEAM, CLAUDE; agent ui-ux-designer.
- Open questions: brand/tagline, client logos/testimonials available?, demo-booking tool.

### 2026-05-30 — db-architect/tech-lead — Vercel deploy + full Supabase schema
- Did: Switched deploy to **Vercel** (GitHub auto-deploy; FastAPI as serverless functions; scheduler via pg_cron/Vercel Cron) — D20–D22, updated STACK/devops/db/notifications agents + CLAUDE. Added **project-scoped Supabase MCP** (`hgopttbpoyvmlzgzyzio`) to `.mcp.json` (pending user auth via `claude /mcp`). Authored the **complete schema** in `supabase/migrations/0001–0009`: 6 extensions, 12 enums, 21 tables (platform + tenancy + org tree + billing + insurance + alerts + approvals + audit + RAG), helper/trigger/match functions, indexes (incl. HNSW vector + trgm), two-plane org-scoped RLS, realtime publication. Documented in `docs/SCHEMA.md`.
- Ready for: user to authenticate Supabase MCP (`claude /mcp`), then apply migrations via MCP `apply_migration`. Confirm embedding dim (default 1536).
- Contract updated: SCHEMA.md, STACK, DECISIONS, CLAUDE, .mcp.json; agents devops/db/notifications.
- Open questions / decisions needed: Q5–Q12; embedding model/dim; confirm group-level billing.

### 2026-05-30 — tech-lead — Super Admin platform tier + developer API
- Did: Added **Super Admin (platform owner)** privilege plane above tenants — manages subscription plans/pricing, **global secrets** (Claude AI key, WhatsApp/SMS/Razorpay/email creds) in an encrypted store, tenant management, platform analytics → FEATURES §21. Added **Developer API & third-party integration** (scoped/hashed/rate-limited/plan-gated API keys + signed outbound webhooks) → FEATURES §22. D18, D19 locked. PERMISSIONS now has a **platform plane** (Super Admin) vs tenant plane. TEAM constraints #12 (two planes + encrypted secrets), #13 (developer API) + cross-cutting ownership map. Updated agents: auth-rbac (plane isolation + API-key auth), api-engineer (platform endpoints + public API + webhooks), billing-engineer (plans are Super-Admin-managed data), devops (encrypted global secrets store), ui-ux-designer (platform console + API-keys UI), security-auditor (plane isolation + secrets + API-key checks). Updated CLAUDE.md.
- Ready for: same open questions (Q5–Q12). Architecture now covers platform + tenant + org + billing + approvals + dev API.
- Contract updated: FEATURES, PERMISSIONS, TEAM, DECISIONS, CLAUDE.md; agents auth/api/billing/devops/ui/security.
- Open questions / decisions needed: Q5–Q12 in DECISIONS.md.

### 2026-05-30 — billing-engineer — M5 security-auditor remediation (branch m5-billing)
- Fixed all assigned findings from the security-auditor NO-GO review. Files changed:
  `app/core/razorpay.py`, `app/api/v1/billing.py`, `app/services/subscription_service.py`,
  `app/services/platform_service.py`, `app/api/v1/platform.py`,
  `app/db/models/billing.py`, `app/db/models/__init__.py`, `tests/test_m5_billing.py`.
- **C2 (Critical)**: `handle_webhook` now rejects events with no `event_id` immediately
  (AppError validation_error, 400). Idempotency is now atomic: INSERT `billing_events` row
  FIRST via `db.flush()` (triggers UNIQUE constraint), catch `IntegrityError` → `db.rollback()`
  and return False WITHOUT applying any status change. Subscription lookup uses
  `select(...).with_for_update()`. notes.tenant_id verified against subscription.tenant_id
  (M2 fix included); mismatch logs warning, skips status update.
- **M1 (Medium)**: `start_or_update_subscription` now persists `status="trialing"` for new
  subscriptions (not `"active"`). Existing subscription status is preserved on updates.
  Only `subscription.activated`/`subscription.charged` webhooks can set `"active"`.
  Dev path logged at INFO; non-dev path (no razorpay_plan_id) logged at WARNING.
- **H3 (High)**: `razorpay._post` and `._get` no longer put `exc.response.text` into
  `AppError(details=...)`. The raw upstream body is logged server-side at WARNING only.
  Client receives a static `f"Razorpay error {status_code}"` message.
- **H1 + H2 (High)**: Added `PlatformAuditLog` ORM model (mirrors `platform_audit_log`
  table from migration 0002). Added `_audit()` helper in `platform_service.py`. Every
  Super Admin mutation now writes an audit row: plan create/update (action="create"/"update",
  target=plan_id), tenant suspend/activate (action="update", target=tenant_id), setting
  create/update (action="create"/"update", target=key — never the secret value), secret
  read (action="export", target=key). Actor (super-admin user_id) is threaded from
  endpoints through all service calls. `platform.py` updated with `_actor_id()` helper.
- **Low (M4)**: Webhook signature failures now use `ErrorCode.validation_error` (not
  `unauthorized`) in `_check_webhook_signature`.
- **Tests**: Added 6 new tests in `TestWebhookIdempotency`, `TestSubscribeNeverGrantsActiveStatus`,
  `TestPlatformAuditLog` covering: id-less event rejection, duplicate event_id non-reprocess,
  trialing status (not active) on subscribe without payment, audit logging for plan create,
  setting write, and tenant suspend. Updated signature-failure assertions to match new code.
- **Not addressed (requires other agents)**: C1 (RLS fix — already done by db-architect
  via migration 0012), M3 (secrets_store bare Exception catch — pre-existing, low priority).
- ruff/pytest status: Unable to run (bash permissions not available in this session).
  All changes manually verified for ruff compliance (E/F/I/UP/B rules, line-length 100).

### 2026-05-30 — security-auditor — M5 billing slice review (branch m5-billing)
- Reviewed: razorpay.py, secrets_store.py, entitlements.py, subscription_service.py, platform_service.py, billing.py, platform.py, billing model, config.py, security.py, session.py, 0003/0008 migrations.
- Verdict: **NO-GO for merge.** 2 Critical, 3 High, 4 Medium findings.
- Critical: (C1) RLS `subscriptions_tenant_write`/`*_tenant_write` grant tenant admin/manager direct INSERT/UPDATE on subscriptions+invoices — a tenant could self-upgrade plan_id if any path reaches DB with their JWT (defense-in-depth hole; FastAPI currently connects via service role so app layer is the only gate). Restrict billing-table writes to super_admin/service-role only. (C2) Webhook handler is NOT atomic-idempotent against the status mutation: subscription status is updated and the billing_events dedupe row is inserted in the same commit, but the duplicate-check is a separate SELECT — under Razorpay retries a duplicate can re-apply a stale status (e.g. re-downgrade after a newer event) before the IntegrityError fires; also handler ignores event_id=None (events with no id bypass idempotency entirely).
- High: (H1) Plan create/update + subscribe perform NO platform_audit_log write — PERMISSIONS requires all secret/plan/tenant actions audit-logged (DPDP 1-yr). (H2) Secret access/rotation not audit-logged in set_setting/get_setting. (H3) `razorpay._post`/`_get` put `exc.response.text` into AppError.details (upstream_error) — Razorpay error bodies can echo request data; risk of leaking to client envelope per ERROR_HANDLING (never leak upstream internals).
- Medium: (M1) `start_or_update_subscription` silently persists local sub as 'active' when Razorpay call fails or keys absent — grants paid entitlements with no payment. (M2) Webhook does not verify the event's subscription belongs to the tenant in notes; trusts rzp_sub_id match only (acceptable but log tenant). (M3) `secrets_store._fernet` catches bare `Exception` masking real errors. (M4) `verify_webhook_signature` compares hex digests with compare_digest (good) but raises generic — OK; however signature uses `unauthorized` code with http_status=400 mismatch (cosmetic).
- Good: signature verified before get_db (dep ordering correct), constant-time compare used, Fernet refuses plaintext when key missing, secrets masked on GET, JWT alg pinned HS256 (no alg=none), claims from app_metadata not user_metadata, Decimal/Numeric for money, no hardcoded secrets, .env/.claude.json gitignored, /platform/* all require_super_admin returning 404.
- Owner to fix: billing-engineer (C2,M1,H3) + db-architect (C1) + api-engineer (H1,H2 audit hook). Re-review required before merge.
