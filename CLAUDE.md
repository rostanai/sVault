# sVault

**Corporate Insurance Portfolio & Renewal Management System** — an internal web app for an India-based
company to manage its OWN insurance policies (Vehicle, Machinery, Plant, Factory, Employees, Key-person,
Stock RM/FG), replacing manual Excel. Core value: a dashboard + in-app document vault + **multi-channel
renewal alerts (WhatsApp/Telegram/SMS/email)** so renewals are never missed, plus **AI "Ask sVault"** RAG
over policy documents. Built by an AI development team of Claude Code subagents.

## Read these first (no knowledge gaps)
- `docs/PRD.md` — product requirements (consolidated) + release phases
- `docs/BUILD_PLAN.md` — milestones M0–M9, epics, agent owners, gates
- `docs/PROJECT_BRIEF.md` — product, users, roles, entities, flows
- `docs/STACK.md` — pinned 2026 tech versions (source of truth)
- `docs/RESEARCH.md` — verified market, competitors, India DLT + DPDP compliance facts
- `docs/FEATURES.md` — full feature catalog (🟢MVP / 🟡P1 / 🔵P2), incl. AI/RAG (§9A)
- `docs/DECISIONS.md` — locked decisions + open questions
- `docs/PERMISSIONS.md` — role × permission matrix
- `docs/SCHEMA.md` — full database schema (Supabase); migrations in `supabase/migrations/`
- `docs/MARKETING.md` — public marketing-website spec
- `docs/CONSIDERATIONS.md` — gap/risk register (check before building)
- `docs/ERROR_HANDLING.md` — error-handling & debugging standard
- `docs/TEAM.md` — the agent team, coordination, and key domain constraints
- `docs/HANDOFFS.md` — append-only log of who did what

## The team (in `.claude/agents/`) — 12 agents
`tech-lead` (master orchestrator) coordinates 11 specialists: `project-setup`, `db-architect`,
`api-engineer`, `auth-rbac-engineer` (Google OAuth, multi-tenant), `billing-engineer` (Razorpay,
plans, trial, feature-gating), `notifications-engineer` (alert engine), `ui-ux-designer` (app + marketing site),
`search-engineer` (search + RAG), `devops-engineer` (deploy + observability), `qa-test-engineer` (testing),
`security-auditor` (DPDP + merge gate).
Start non-trivial work by delegating to **`tech-lead`** — it plans, delegates, integrates, and can
update any subagent's skills.

## How coordination works
Subagents can't call each other (only the tech-lead holds the Task tool). They communicate via the
tech-lead as a hub and via shared contract files in `docs/` (SCHEMA, API_CONTRACT, PERMISSIONS,
HANDOFFS). Each specialist reads the contracts it depends on, updates its own, and logs a handoff.

## Stack (see docs/STACK.md)
FastAPI 0.136 + Pydantic v2 + Python 3.13 (uv) · Supabase (Postgres+Auth+Storage, RLS, pgvector) ·
Next.js 16 + React 19 + Tailwind v4 + shadcn/ui · **Vercel** deploy (GitHub auto-deploy) · Claude API (RAG).
Supabase project `hgopttbpoyvmlzgzyzio`; migrations in `supabase/migrations/`; scheduler via pg_cron/Vercel Cron.

## Non-negotiable domain constraints (see docs/TEAM.md)
- **Multi-tenant SaaS, high scale**: every record carries `tenant_id` + `org_id`; authz + RLS + search tenant/org-scoped (full isolation). Design for scale (async, pooling, queue-based alerts, pagination).
- **Org hierarchy**: tenant = corporate group (**parent + subsidiaries**); parent admins roll up, subsidiaries isolated.
- **Approval workflows**: configurable actions routed by role/permission (+ hierarchy), with **self-approval** where permitted; audit-logged.
- **Two privilege planes**: **Super Admin** (platform owner) above all tenants — manages plans/pricing, global secrets (AI/channel/Razorpay keys), tenants, analytics; NOT a tenant role; global secrets encrypted.
- **Developer API**: public, API-key-authenticated (scoped, hashed, rate-limited, plan-gated) third-party integration + signed webhooks.
- **Feature-gating server-side**: gated actions checked vs the tenant's plan entitlements + limits; Razorpay webhooks sync state. UI gating is convenience only.
- India **SMS = TRAI DLT** transactional templates · **WhatsApp** utility templates · alert cadence **60/30/15/7/1d** + escalation.
- **DPDP** (Data Fiduciary): encryption at rest, RLS, 1-yr audit log, breach notification, employee-PII minimisation.
- **Permission-aware RAG/search**: pgvector retrieval RLS-filtered — never leak a doc a user can't see.
- **INR + GST** localization · **Razorpay** billing · **14-day trial** · **Google OAuth** · in-app subscription/upgrade page.

## Connected tooling
- **GitHub MCP** → repo github.com/rostanai/sVault (devops/CI)
- **Supabase MCP** → database (db-architect)
- **Stitch MCP** → design project `projects/10530408406746453783` (ui-ux-designer)
- Skills: `ui-ux-pro-max`, `supabase`, `supabase-postgres-best-practices`, `claude-api` (RAG)
- **Razorpay** (billing) · **Google OAuth** (auth) — see `billing-engineer` / `auth-rbac-engineer`
