# sVault — Gaps, Risks & Things Not Yet Considered

> A living register of what we haven't covered. Priority: 🔴 critical / go-live blocker · 🟠 important · 🟡 later.
> Owner column = which agent should handle it.

## A. Engineering correctness (easy to forget, expensive to retrofit)
| # | Item | Pri | Owner |
|---|------|:--:|-------|
| A1 | **Timezone for alerts** — expiry/lead-day math must be computed in a defined TZ (IST default; store tenant TZ). "60 days before" + send windows depend on it. | 🔴 | notifications, db |
| A2 | **Supabase connection pooling on serverless** — Vercel functions exhaust direct Postgres connections. Use **Supavisor / transaction pooler** (pooled connection string), not the direct one. | 🔴 | devops, api |
| A3 | **File-upload security** — allowed types, size caps, **malware/virus scan**, signed URLs for download, private Storage buckets, no public access. | 🔴 | api, security |
| A4 | **Idempotency & retries** for webhooks/jobs (Razorpay, notifications, outbound webhooks) + dead-letter handling. | 🟠 | billing, notifications |
| A5 | **Backups & disaster recovery** — Supabase PITR enabled, periodic restore drills, documented RTO/RPO. | 🔴 | devops |
| A6 | **Testing strategy** — unit + integration + **E2E** (Playwright) + load test for alert dispatch at scale. No QA owner yet. | 🟠 | (new QA agent) |
| A7 | **Observability** — error tracking (Sentry), structured logs, uptime monitoring, **status page**, on-call alerts for platform outages (≠ insurance alerts). | 🔴 | devops |
| A7b | **Error handling & debugging standard** — error envelope + codes, request_id tracing, 404-not-403 for cross-tenant, retries/circuit-breakers/idempotency/dead-letter, frontend error boundaries. ✅ specced in `docs/ERROR_HANDLING.md`. | 🔴 | api, ui, devops |
| A8 | **Cost monitoring & caps** — WhatsApp/SMS per-message + **Claude API token** + Vercel/Supabase usage can spike at scale. Budgets, alerts, per-plan AI rate limits, **prompt caching**. | 🟠 | billing, devops, search |
| A9 | **Email deliverability** — SPF/DKIM/DMARC, dedicated sending domain, bounce/complaint handling, unsubscribe. | 🟠 | notifications, devops |
| A10 | **Staging environment** + seed data; preview ≠ prod data. | 🟠 | devops |
| A11 | **Soft-delete & data retention** policy (vs hard delete); audit-log immutability + 1-yr retention purge job. | 🟠 | db, security |
| A12 | **Rate limiting / WAF / bot protection** at the edge (Vercel/Cloudflare) beyond per-API-key limits. | 🟠 | devops, api |

## B. Security & privacy (beyond current security-auditor scope)
| # | Item | Pri | Owner |
|---|------|:--:|-------|
| B1 | **PII → LLM data residency** — RAG sends employee/policy data to **Claude (US)**. Need DPA with Anthropic, consider **PII redaction before embedding/prompting**, document the cross-border transfer under DPDP. | 🔴 | security, search |
| B2 | **Sub-processor DPAs** — signed Data Processing Agreements with Supabase, Vercel, Razorpay, Meta/WhatsApp BSP, Anthropic, email/SMS vendors. | 🔴 | security |
| B3 | **DPDP Grievance Officer + Data-Principal rights** — appoint officer, build export/delete/correction request flow, consent records. | 🔴 | security, api |
| B4 | **CAPTCHA / trial-abuse prevention** on signup (stop trial farming, bots). | 🟠 | auth, ui |
| B5 | **Security headers + CSP + CORS** policy; secure cookies (HttpOnly/SameSite). | 🟠 | api, devops |
| B6 | **Pen test + dependency scanning** (Dependabot/`pip-audit`/`npm audit`) before launch. | 🟠 | security, devops |
| B7 | **Secrets rotation** procedure for the encrypted global secrets (AI/channel/Razorpay keys). | 🟠 | devops, security |
| B8 | **Document sensitivity** — insurance docs hold financial/employee PII; consider watermarking, access logging, download limits. | 🟡 | security |

## C. Notifications — operational lead times (start EARLY)
| # | Item | Pri | Owner |
|---|------|:--:|-------|
| C1 | **WhatsApp BSP onboarding** — pick a BSP (Meta direct / Gupshup / MSG91 / Twilio), verify business, get a number, **template approval** (utility), opt-in capture, 24h session window, per-message cost. Takes weeks. | 🔴 | notifications |
| C2 | **SMS DLT registration** — entity + header + **content template** approval on a DLT portal (days–weeks). Without it, SMS is silently dropped. | 🔴 | notifications |
| C3 | **Notification preferences** — per-user opt-in/opt-out, quiet hours, per-recipient dedup & rate limiting. | 🟠 | notifications, api |

## D. Product / business
| # | Item | Pri | Owner |
|---|------|:--:|-------|
| D1 | **Customer support** — helpdesk/ticketing, knowledge base, in-app chat, contact SLA. | 🟠 | product |
| D2 | **Product analytics** — funnel/activation tracking (PostHog/Mixpanel), the "day-2 activation" metric. | 🟠 | product, ui |
| D3 | **GST e-invoicing / TDS** — compliant B2B invoices, GSTIN capture, e-invoice if turnover threshold; place-of-supply logic. | 🟠 | billing |
| D4 | **Plan pricing finalization** + free-tier decision (still open Q6/Q8). | 🔴 | billing |
| D5 | **Feedback / NPS / feature requests** capture. | 🟡 | product |
| D6 | **SLA / uptime commitments** for paid tiers. | 🟡 | product, devops |

## E. Data model additions to consider
| # | Item | Pri |
|---|------|:--:|
| E1 | Policy: deductible, coverage details/exclusions, location/asset register, beneficiaries, claim history, currency, tags, notes/activity feed | 🟠 |
| E2 | **Premium installment** schedule + reminders (separate from expiry) | 🟠 |
| E3 | **Claims** module (Phase 2) linked to policies | 🟡 |
| E4 | Tenant-level **branding/settings** (logo in alert templates, default cadence, TZ) | 🟠 |
| E5 | Excel **import mapping + validation UI** (their real migration is messy data) | 🟠 |

## F. Team / process gaps
| # | Item | Pri |
|---|------|:--:|
| F1 | **QA / test engineer agent** — currently no owner for E2E/load/test strategy | 🟠 |
| F2 | **Observability/SRE** ownership — fold into devops or split out | 🟠 |
| F3 | **Technical writer / docs** — user docs, API docs, in-app help | 🟡 |
| F4 | **Data-migration** ownership for the Excel→sVault onboarding | 🟡 |

## Top go-live blockers (do early)
A1 timezone · A2 connection pooling · A5 backups · A7 observability · B1 PII→LLM · B2 DPAs · B3 grievance officer/rights · C1 WhatsApp BSP · C2 SMS DLT · D4 pricing.
