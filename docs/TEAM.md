# sVault — Agent Team & Coordination Protocol

> sVault = **Corporate Insurance Portfolio & Renewal Management System** (internal, India-based).
> See `docs/PROJECT_BRIEF.md` (product), `docs/RESEARCH.md` (verified market/compliance), `docs/FEATURES.md` (full catalog).

## Roster (12 agents)
| Agent | Role | Model | Owns these contract files |
|-------|------|-------|---------------------------|
| `tech-lead` | **Master** orchestrator/architect — plans, delegates, manages & updates the team | opus | all (hub) |
| `project-setup` | Scaffolds repo, tooling, skeletons | sonnet | repo structure, README |
| `db-architect` | Schema, migrations, RLS, indexes (Supabase) | sonnet | `docs/SCHEMA.md` |
| `api-engineer` | REST API — FastAPI + Pydantic v2 | sonnet | `docs/API_CONTRACT.md` / OpenAPI |
| `auth-rbac-engineer` | Auth (Google OAuth), roles, permissions, JWT, multi-tenant | opus | `docs/PERMISSIONS.md` |
| `billing-engineer` | **Subscriptions, Razorpay, 14-day trial, feature-gating/entitlements** | sonnet | `docs/PLANS.md` |
| `notifications-engineer` | **Renewal-alert engine** — WhatsApp/Telegram/SMS-DLT/email, scheduler, escalation | sonnet | alert config, delivery log |
| `ui-ux-designer` | UI/UX in Stitch + Next.js frontend | sonnet | Stitch project, components |
| `search-engineer` | Full-text + pgvector search **+ RAG ("Ask sVault")** | sonnet | search indexes, RAG pipeline |
| `devops-engineer` | Docker, CI/CD, deploy, secrets | sonnet | `.github/workflows`, Docker |
| `qa-test-engineer` | **Testing & quality** — unit/integration/E2E/load + tenant-isolation tests; merge gate | sonnet | test suites, coverage |
| `security-auditor` | Security review + **DPDP compliance** (read-only) | opus | findings reports |

## Document map (read what your job depends on)
- `docs/PROJECT_BRIEF.md` — what sVault is, entities, roles, flows (all)
- `docs/STACK.md` — pinned 2026 versions (all)
- `docs/RESEARCH.md` — verified market, competitors, India DLT + DPDP facts (all)
- `docs/FEATURES.md` — full feature catalog with 🟢MVP/🟡P1/🔵P2 tags (all)
- `docs/DECISIONS.md` — locked decisions + open questions (all)
- `docs/SCHEMA.md` — full DB schema reference (db; api, search read)
- `docs/MARKETING.md` — public marketing-site spec (ui-ux-designer)
- `docs/CONSIDERATIONS.md` — gap/risk register (all — check before building your slice)
- `docs/PRD.md` — product requirements (all) · `docs/BUILD_PLAN.md` — milestones/epics/owners (all)
- `docs/ERROR_HANDLING.md` — error & debugging standard (all)
- `docs/SCHEMA.md` — tables + RLS (db writes; api, search, notifications read)
- `docs/API_CONTRACT.md` / OpenAPI — endpoints + schemas (api writes; ui, notifications read)
- `docs/PERMISSIONS.md` — role × permission matrix (auth writes; api, ui, db read)
- `docs/HANDOFFS.md` — append-only log; every agent adds an entry when done

## Key domain constraints — EVERY agent must honor these (verified in RESEARCH.md)
1. **India SMS = TRAI DLT**: alerts must use registered **transactional/service** templates (brand name, whitelisted CTA links; no DND, 24/7). Promo window 10:00–21:00 IST does not apply to transactional. (notifications + devops)
2. **WhatsApp** = pre-approved **utility** template messages, honor opt-in. (notifications)
3. **DPDP Act 2023 + Rules 2025** (notified 2025-11-13): app is a **Data Fiduciary** storing employee PII. Required: **encryption at rest**, strict access control (RLS), **audit log with 1-year retention**, **breach-notification** workflow (Board + individuals). Consider **data-minimising** employee group-health to policy-level. (db, auth, security, devops)
4. **Permission-aware RAG/search**: pgvector retrieval MUST be RLS-filtered — never return a document/chunk a user can't access. (search, db, auth)
5. **Alert cadence default 60/30/15/7/1 days** before expiry, with escalation. (notifications, api, ui)
6. **INR + GST** on premiums; currency/formatting India-localized. (api, ui)
7. **Multi-tenant SaaS**: every record carries `tenant_id`; all authz + RLS + search are tenant-scoped; data fully isolated between tenants. (db, auth, api, search, all)
8. **Feature-gating is server-side**: gated actions checked against the tenant's plan entitlements + limits via the entitlement layer — UI gating is convenience only. Razorpay webhooks keep entitlement state in sync. (billing, api, ui)
9. **Org hierarchy**: tenant = corporate group with **parent + subsidiary** companies. Every record carries `tenant_id` + `org_id`. Parent admins roll up across subsidiaries; subsidiaries are isolated from each other. RLS + search + permissions are org-scoped. (db, auth, api, search, ui, all)
10. **Approval workflows**: configurable actions (renewal, new policy, vendor, high-value) route to an approver by **role/permission** (and org hierarchy), with **self-approval** where the role permits. All approvals audit-logged; approval notifications via notifications-engineer. (api, auth, notifications, ui, db)
11. **High scale**: design for many tenants — async I/O, DB connection pooling, indexed queries, **queue-based** alert dispatch, pagination everywhere, horizontal-scalable stateless API. (db, api, notifications, devops)
12. **Two privilege planes**: **Super Admin (platform owner)** sits ABOVE all tenants — manages plans/pricing, global secrets (AI/WhatsApp/SMS/Razorpay/email keys), tenants, analytics. NOT a tenant role; hard-isolated routes; all actions audit-logged. Global secrets live **encrypted** (never plaintext/client). (auth, api, devops, security, ui)
13. **Developer API**: public, OpenAPI-documented, **API-key-authenticated** (hashed, scoped, rate-limited, plan-gated `feature:api`) third-party integration surface + signed outbound webhooks. (api, auth)
14. **Timezone discipline**: all expiry/lead-day/scheduling math in a defined TZ (IST default; store tenant TZ) — never naive local time. (notifications, db, api)
15. **Serverless DB access**: use Supabase **transaction pooler (Supavisor)** connection string from Vercel functions, never the direct connection. (api, devops)
16. **PII → LLM caution**: RAG/AI sends data to Claude (US) — redact/minimise PII before embedding/prompting, document cross-border transfer under DPDP, DPA with Anthropic. (search, security)
17. **File uploads**: private Storage buckets, signed URLs, type/size limits, malware scan — never public. (api, security)
18. **Error handling & debugging** (`docs/ERROR_HANDLING.md`): consistent error envelope + code taxonomy + **request_id** tracing; never leak stack traces/PII; **404 not 403** for cross-tenant access; timeouts/retries/circuit-breakers + idempotency + dead-letter on all external calls; frontend error boundaries; structured logs + Sentry. (api, ui, devops, qa, security)
> Full backlog of gaps/risks (observability, backups, DPAs, BSP/DLT lead times, cost caps, testing) is in `docs/CONSIDERATIONS.md`; error/debug standard in `docs/ERROR_HANDLING.md`.

## Platform-admin & developer-API ownership (cross-cutting — no single agent, so explicit)
- Plans/pricing/entitlement-map CRUD → **billing-engineer** (+ Super-Admin UI by ui-ux-designer)
- Super-Admin role + plane isolation + API-key auth → **auth-rbac-engineer**
- Platform-admin endpoints + public developer API + webhooks-out → **api-engineer**
- Encrypted global secrets store + rotation → **devops-engineer** (reviewed by security-auditor)
- Platform console + API-keys UI → **ui-ux-designer**

## How agents communicate
Specialists **cannot** call each other — only the `tech-lead` (holds the Task tool) delegates. Communication = (1) tech-lead as hub routing results between specialists, and (2) the shared contract files above. Each agent reads its dependencies, updates its own contract file, and logs a `HANDOFFS.md` entry.

## HANDOFFS.md entry format
```
### <date> — <agent> — <task>
- Did: <what changed>
- Ready for: <which agent / what's unblocked>
- Contract updated: <file(s)>
- Open questions / decisions needed: <...>
```

## Master manages the team
The `tech-lead` owns the `.claude/agents/*.md` files and can edit a subagent's skills, add a new specialist, or retire one — then logs it in `HANDOFFS.md` and tells the user.

## Typical build sequence
`project-setup` → `db-architect` → `auth-rbac-engineer` (+RLS) → `api-engineer` → `notifications-engineer` + `search-engineer`/RAG → `ui-ux-designer` → `devops-engineer` → `qa-test-engineer` + `security-auditor` (merge gates). The tech-lead parallelizes where dependencies allow.
