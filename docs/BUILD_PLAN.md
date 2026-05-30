# sVault — Build Plan

> Execution plan for the PRD. Milestones M0→M9, epics, agent owners, and gates. The `tech-lead`
> drives this, delegating epics to specialists. Dependencies drive order; parallel where possible.

## How to read
- **Gate** = must pass before the milestone is "done": code + tests (qa) + security check + CI green.
- External long-lead items (WhatsApp BSP, SMS DLT, DPAs, Razorpay KYC) run **in parallel** — see `START_NOW.md`.
- Build against **test/sandbox** modes while approvals pend.

---

## PHASE 0 — MVP

### M0 — Foundation & infra
- **Epic FND**: monorepo scaffold (backend FastAPI + frontend Next.js), uv, ruff, CI (lint+test), `.env.example`. → `project-setup`
- Vercel project + GitHub auto-deploy; Supabase project wired (pooler conn, extensions, PITR). → `devops`
- Apply DB migrations `0001–0009` via Supabase MCP. → `db-architect`
- Error-envelope + request-id middleware + Sentry skeleton. → `api`, `devops`
- **Gate**: `/health` green on a Vercel preview; migrations applied; CI runs.

### M1 — Identity, tenancy, org, RBAC
- **Epic AUTH**: Google OAuth + email/password, signup→tenant+admin+**14-day trial**, invitations, sessions. → `auth-rbac`
- **Epic ORG**: parent+subsidiary tree; JWT tenant/org/role claims; `accessible_org_ids()` roll-up; RLS live. → `auth-rbac` + `db`
- **Gate (critical)**: qa **tenant/org isolation** tests pass (A can't see B; subsidiary can't see sibling); plane isolation. → `qa` + `security`

### M2 — Policies & document vault
- **Epic POLICY**: CRUD, 8 categories, fields, auto-status, renewal chain, search/filter/sort, providers. → `api` + `db` + `ui`
- **Epic DOC**: upload to private Supabase Storage (signed URLs, type/size limits, scan hook), library. → `api` + `ui` + `security`
- **Gate**: policy lifecycle works end-to-end with RLS; docs secure.

### M3 — Dashboard
- **Epic DASH**: status totals, upcoming expiries (30/60/90), at-risk, breakdowns; realtime updates. → `ui` + `api`
- **Gate**: dashboard reflects real data, role/org-scoped.

### M4 — Renewal alert engine (the differentiator)
- **Epic ALERT**: cadence 60/30/15/7/1; scheduler via **pg_cron/Vercel Cron**; **WhatsApp + Email**; delivery log; idempotency; **IST timezone** math. → `notifications` + `api`
- **Gate**: alerts fire at correct lead times (timezone-correct), no double-send, delivery logged. (WhatsApp via test number until BSP live.)

### M5 — Billing, trial, entitlements, super-admin
- **Epic BILLING**: plans/tiers, **Razorpay** subscriptions (test mode), in-app subscription page + **anytime upgrade**, webhooks (idempotent), server-side **entitlement gating**. → `billing` + `api` + `ui`
- **Epic PLATFORM**: super-admin console — plans/pricing CRUD, global secrets (encrypted), tenant mgmt. → `billing` + `api` + `ui` + `auth`
- **Gate**: trial→paid via Razorpay test; gated features enforced server-side; super-admin operates.

### M6 — Approvals (basic) + marketing site + hardening
- **Epic APPROVAL**: renewal approval, role/permission routing, self-approval, inbox, audit. → `api` + `auth` + `ui` + `notifications`
- **Epic MKT**: landing, features, pricing, **legal pages** (Privacy/Terms/Refund — Razorpay req), signup. → `ui-ux-designer`
- **Epic HARDEN**: error handling complete, observability/dashboards, backups verified, security audit, load smoke test. → `devops` + `security` + `qa`
- **Gate = MVP launch readiness**: full security review (DPDP + OWASP), isolation suite green, legal pages live, Razorpay activated, error/obs in place.

**→ MVP SHIPS.**

---

## PHASE 1 (post-MVP)
- **SMS(DLT)+Telegram** channels, escalation, ack/snooze, fallback, notification prefs. → `notifications`
- **AI "Ask sVault"** RAG (pgvector + Claude, permission-aware) + summarization + field-extraction. → `search`
- **Full-text search** in documents. → `search`
- **Group/consolidated dashboards** + cross-subsidiary reporting. → `ui` + `api`
- **OCR + document versioning**; **granular RBAC**; **analytics/reports**. → `search`/`db`/`ui`
- **Developer API + API keys** + outbound webhooks. → `api` + `auth`
- **Onboarding wizard + Excel import**; **billing portal/invoices/GST/dunning**. → `ui` + `billing`

## PHASE 2
- Claims module · premium installments · multi-level approvals + rules engine · integrations (ERP/calendar/SSO) ·
  outbound webhooks GA · mobile/PWA · advanced DPDP tooling (consent, DSAR) · provider portal · i18n · A/B testing.

---

## Milestone dependency chain
M0 → M1 → M2 → {M3, M4, M5} (parallelizable after M2) → M6 → **MVP**.
Auth/org (M1) gates everything (isolation). Billing (M5) needs pricing (Q6) + Razorpay KYC. Alerts (M4) ship on WhatsApp+Email first; SMS waits on DLT (Phase 1).

## Agent ownership quick map
`project-setup`=scaffold · `db-architect`=schema/migrations/RLS · `auth-rbac`=identity/org/approvals-perms ·
`api-engineer`=endpoints/entitlement/errors · `billing`=Razorpay/plans/entitlements · `notifications`=alert engine ·
`search`=search+RAG · `ui-ux-designer`=app+marketing · `devops`=Vercel/Supabase/obs · `qa-test-engineer`=tests/isolation ·
`security-auditor`=DPDP/OWASP gate · `tech-lead`=orchestrates all.
