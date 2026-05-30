# sVault — Product Requirements Document (PRD)

> v1.0 · 2026-05-30 · Owner: tech-lead. Consolidates PROJECT_BRIEF, RESEARCH, FEATURES, DECISIONS,
> SCHEMA, MARKETING, CONSIDERATIONS, ERROR_HANDLING. Detailed feature bullets live in `docs/FEATURES.md`.

## 1. Overview
**sVault** is a high-scale, multi-tenant **B2B SaaS** for managing a company's **own** corporate insurance
portfolio. It replaces manual Excel + scattered email/folder soft-copies with one system of record:
a dashboard, an in-app document vault, **multi-channel renewal alerts** (WhatsApp/SMS/Email/Telegram),
**AI "Ask sVault"** over policy documents, approval workflows, and subscription billing. India-first
(INR/GST, DLT, DPDP). Sold to corporate groups (parent + subsidiaries).

## 2. Goals & success metrics
- **G1 — Zero missed renewals**: every policy gets timely multi-channel alerts. *Metric: % renewals alerted ≥ first lead time; missed-renewal count → 0.*
- **G2 — Single source of truth**: 100% of policies + documents in-app. *Metric: policies migrated, docs uploaded.*
- **G3 — Fast time-to-value**: first value in 2–5 min of signup. *Metric: activation rate (add 1st policy + 1st alert within 48h).*
- **G4 — Convert trials**: *Metric: 14-day trial→paid ≥ 15%.*
- **G5 — Compliant & secure**: DPDP-ready, tenant isolation provable. *Metric: 0 isolation defects; audit passes.*

## 3. Personas & roles
- **Super Admin** (platform owner) — runs the SaaS: plans, global secrets, tenants. *Platform plane.*
- **Tenant Admin** — runs a company group: users, org tree, subscription, settings.
- **Manager** — manages all policies + approvals across the group.
- **Owner** — manages the policies they finalized; receives alerts.
- **Viewer** — read-only.
(Full matrix: `docs/PERMISSIONS.md`.)

## 4. Scope
**In:** policy records + categories, document vault, dashboard, renewal-alert engine, approvals, AI/RAG,
multi-tenant + org hierarchy, subscriptions/billing (Razorpay) + trial + entitlements, super-admin console,
developer API, marketing website, DPDP/security baseline.
**Out (now):** selling/quoting insurance, broker CRM, full claims processing (Phase 2), native mobile (Phase 2).

## 5. Functional requirements (by epic — phase tag 🟢MVP/🟡P1/🔵P2)
> IDs map to epics in `docs/BUILD_PLAN.md`. Exhaustive bullets in `docs/FEATURES.md`.

**FR-AUTH** 🟢 Google OAuth + email/password, multi-tenant signup → tenant+admin+trial, invitations, sessions, password reset. 🟡 MFA. 🔵 SSO/SCIM.
**FR-ORG** 🟢 Parent + subsidiary org tree; tenant+org-scoped access; parent roll-up. 🟡 group/consolidated dashboards, cross-subsidiary reporting, move policy between orgs.
**FR-POLICY** 🟢 CRUD across 8 categories; full field set; auto status; renewal chain; search/filter/sort. 🟡 sub-asset line items, custom fields, bulk import. 🔵 endorsements.
**FR-DOC** 🟢 Upload/store/download soft copies (private, encrypted), library. 🟡 versioning, OCR, AI field-extraction.
**FR-DASH** 🟢 Status totals, upcoming expiries (30/60/90), at-risk, breakdown by category/provider/owner. 🟡 trends, renewal calendar, owner workload.
**FR-ALERT** 🟢 Cadence 60/30/15/7/1; **WhatsApp + Email**; scheduler; delivery log. 🟡 **SMS(DLT)** + Telegram, escalation, ack/snooze, fallback, preferences.
**FR-APPROVAL** 🟢 Renewal approval; role/permission routing; self-approval; audit-logged; inbox. 🟡 multi-level/threshold, delegation, reminders. 🔵 rules engine.
**FR-AI** 🟡 Ask sVault (RAG, permission-aware), summarization, field-extraction. 🔵 gap analysis, renewal assistant, quote comparison. *(Q5: may promote basic to MVP.)*
**FR-SEARCH** 🟢 Policy search/filter. 🟡 full-text in documents. 🔵 semantic search.
**FR-BILLING** 🟢 Plans/tiers, **14-day trial**, **Razorpay** subscriptions, in-app subscription page + anytime upgrade, entitlements (server-side gating), webhooks. 🟡 invoices/GST, portal, proration, coupons, dunning, metering.
**FR-PLATFORM** 🟢 Super-admin console: manage plans/pricing, global secrets (AI/channel/Razorpay), tenant mgmt. 🟡 platform analytics, impersonation, announcements.
**FR-API** 🟢 API-key issue/revoke, public REST API (scoped, rate-limited, plan-gated). 🟡 outbound webhooks, usage logs. 🔵 dev portal/SDKs.
**FR-MKT** 🟢 Marketing site: landing, features, pricing, legal pages, signup. 🟡 solutions, comparisons, blog/SEO, security page, demo. 🔵 case studies, A/B, i18n.
**FR-NOTIF-OPS** 🟢 Notification/delivery log. 🟡 in-app notification center, retries/receipts, per-user prefs.

## 6. Non-functional requirements
- **NFR-SEC** RLS on all tables; tenant+org isolation provable; two privilege planes; encryption at rest; secrets encrypted; OWASP API Top-10; **404-not-403** cross-tenant. (`ERROR_HANDLING.md`, `PERMISSIONS.md`)
- **NFR-PRIV** DPDP: encryption, access control, **1-yr audit-log retention**, breach notification, grievance officer, data-principal rights, sub-processor DPAs, PII→LLM minimisation.
- **NFR-PERF/SCALE** async, Supabase **transaction pooler**, indexed queries, queue-based alerts, pagination, horizontal-scalable serverless; targets for alert dispatch + RAG latency.
- **NFR-AVAIL** health/ready endpoints, PITR backups + DR drills, status page, error budgets.
- **NFR-OBS** structured logs + request_id, Sentry, dashboards, alerting (`ERROR_HANDLING.md`).
- **NFR-COMPLIANCE-IN** TRAI DLT (SMS), WhatsApp utility templates, INR/GST, IST timezone for scheduling.
- **NFR-A11Y/UX** WCAG, responsive, dark mode, loading/empty/error states, first value 2–5 min.
- **NFR-COST** per-plan AI rate limits, prompt caching, channel/LLM cost budgets + alerts.

## 7. Technical architecture (see `docs/STACK.md`, `docs/SCHEMA.md`)
Next.js 16 + React 19 + Tailwind v4 + shadcn/ui (app + marketing) · FastAPI (Python 3.13, uv) REST/OpenAPI
as Vercel serverless functions · Supabase (Postgres + Auth + Storage + pgvector + pg_cron) · Claude API (RAG) ·
Razorpay (billing) · WhatsApp/SMS/Email/Telegram (alerts) · Vercel deploy via GitHub auto-deploy.

## 8. Release plan (phases)
- **Phase 0 — MVP**: the shippable core (all 🟢). Outcome: a company can sign up (trial), add policies + docs, see the dashboard, get WhatsApp+Email renewal alerts, approve renewals, subscribe via Razorpay; super-admin operates the platform; public site converts.
- **Phase 1**: SMS(DLT)+Telegram + escalation, AI "Ask sVault", full-text search, group dashboards/reporting, OCR/versioning, granular RBAC, analytics, developer API, onboarding wizard + Excel import, billing portal/dunning.
- **Phase 2**: claims, installments, multi-level approvals/rules engine, integrations (ERP/calendar/SSO), webhooks, mobile/PWA, advanced DPDP tooling, provider portal, i18n.

## 9. Open decisions (block/shape build — see `docs/DECISIONS.md`)
Q5 promote AI to MVP? · Q6 pricing · Q7 employee-PII minimisation · Q8 free-tier vs paywall ·
Q10 group vs per-subsidiary billing · Q11 which actions need approval + thresholds · Q12 who self-approves.

## 10. Acceptance (definition of done per phase)
Each phase ships only when: features meet FRs, NFR-SEC isolation tests pass (qa + security gates), CI green,
error handling + observability in place, and the relevant `START_NOW.md` external items are live (e.g. DLT before SMS).
