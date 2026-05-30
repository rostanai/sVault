# sVault — Decisions Log

> Locked decisions + open questions. Updated as the project progresses. Every agent reads this.

## Locked decisions
| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Product = internal **Corporate Insurance Portfolio & Renewal Mgmt System** (not selling insurance) | user problem statement |
| D2 | Stack = **FastAPI + Supabase Postgres + Next.js 16** (see STACK.md) | matches connected MCP tools |
| D3 | **8 policy categories**: Vehicle, Machinery, Plant, Factory, Employees (group health/GPA), Key-person, Stock (RM/FG) — extensible | problem statement |
| D4 | **Multi-channel alerts**: WhatsApp + Email + SMS(DLT) + Telegram; default cadence **60/30/15/7/1 days** + escalation | core differentiator; RESEARCH §4 |
| D5 | **Permission-aware RAG ("Ask sVault")** via pgvector + Claude API, RLS-filtered | differentiator; RESEARCH (AI) |
| D6 | **No e-signature** feature | user instruction |
| D7 | DPDP-compliant by design: encryption at rest, RLS, 1-yr audit log, breach-notification hooks | Data Fiduciary, RESEARCH §5 |
| D8 | India localization: **INR + GST** | India-based company |
| D9 | **Multi-tenant SaaS** — sVault is sold to multiple companies (resolves Q1) | subscription/plans imply SaaS |
| D10 | **Subscription plans** with **server-side feature-gating/entitlements** (Free/Starter/Professional/Enterprise) | FEATURES §16–17 |
| D11 | **Razorpay** payment gateway (Subscriptions, UPI Autopay/eMandate/cards, webhooks) | India recurring billing |
| D12 | **14-day free trial** started at sign-up; **Google OAuth** + email/password auth | FEATURES §18 |
| D13 | **High scale** SaaS — design for many tenants/policies/users (async, pooling, indexing, queue-based alerts, horizontal scale) | user confirmed |
| D14 | Alert channels priority = **WhatsApp + Email + SMS** (Telegram = supplementary) | user confirmed (resolves Q3) |
| D15 | **Approval workflows** in scope, role/permission-routed, with **self-approval** where permitted | user confirmed (resolves Q4) |
| D16 | **Org hierarchy**: tenant = corporate group with **parent + subsidiary** companies; parent rolls up, subsidiaries scoped | user confirmed |
| D17 | **In-app subscription page** (all plans + INR cost) with **anytime upgrade** via Razorpay → **MVP** | user confirmed |
| D18 | **Super Admin (platform owner)** tier above tenants — manages plans/pricing, global secrets (AI/channel/Razorpay keys), tenants, analytics; separate console; encrypted secrets | user confirmed |
| D19 | **Developer API + API keys** for third-party integration (scoped, hashed, rate-limited, plan-gated `feature:api`) + outbound webhooks | user confirmed |
| D20 | **Vercel** for dev + production; **GitHub → Vercel auto-deploy** (PR preview, main = prod). FastAPI as Vercel Python serverless functions | user confirmed |
| D21 | **Supabase** project `hgopttbpoyvmlzgzyzio`; migrations via **Supabase migrations** + MCP; DB+Auth+Storage | user confirmed |
| D22 | Scheduler via **Supabase pg_cron / Vercel Cron** hitting an endpoint (serverless = no persistent worker) | architecture |
| D23 | **Marketing website** (public, outcome-driven, SEO) to showcase features + drive trial signups; owned by ui-ux-designer; spec in `docs/MARKETING.md`. Legal pages (Privacy/Terms/Refund) required for Razorpay onboarding | user confirmed |

## Open questions (need user input before/at build)
| # | Question | Impacts |
|---|----------|---------|
| Q5 | Promote **basic "Ask sVault" AI + field-extraction into MVP**, or keep Phase 1? | MVP scope |
| Q6 | **Plan pricing** — confirm tiers + INR prices + limits (see FEATURES §16 draft map)? | billing |
| Q7 | **Data-minimise employee group-health PII** (policy-level vs member-level)? | DPDP exposure |
| Q8 | After trial: **Free tier** offered, or trial → must-pay (no free tier)? | monetization |
| Q10 | **Subscription scope** — billed at parent/group level (one account for all subsidiaries), or per-subsidiary? | billing + org model |
| Q11 | **Which actions need approval** (renewals only, or also new policy / vendor / high-value) + **amount thresholds**? | approval workflow |
| Q12 | Which **roles can self-approve** which actions? | approval + permissions |

## Default assumptions (until user says otherwise)
- A1: **Multi-tenant SaaS** — shared schema + RLS `tenant_id` isolation (recommended over schema-per-tenant).
- A2: WhatsApp is the **priority** alert channel; email is the reliable fallback.
- A3: MVP = reminders only (no approval workflow yet).
- A4: Store employee insurance at **policy level**, not individual member records (DPDP minimisation).
- A5: After the 14-day trial, a limited **Free tier** exists (not trial→hard-paywall) — confirm via Q8.
- A6: Plan tiers = **Free / Starter / Professional / Enterprise** per FEATURES §16 draft (prices TBD).
- A7: Tenant = corporate group; **subscription billed at parent/group level** (one account covers subsidiaries) — confirm Q10.
- A8: **Renewals + new policy + high-value premium** require approval; Admin/Manager can **self-approve**; Owner cannot — confirm Q11/Q12.
- A9: Org isolation = shared schema with **`tenant_id` + `org_id`** RLS scoping (not schema-per-tenant).
