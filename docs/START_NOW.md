# sVault — "Start Now" Checklist (long-lead items)

> These have external review/approval times or block other work. Start them **in parallel with development**
> so they don't delay launch. Owner "You" = business/founder action; "Agent" = the dev team handles it.
> Lead time = how long the external process typically takes.

## 🔴 Critical path — begin immediately
| # | Item | Why it's urgent | Owner | Lead time | Done |
|---|------|-----------------|-------|-----------|:---:|
| 1 | **WhatsApp Business API via a BSP** (pick Meta-direct / Gupshup / MSG91 / Twilio). Verify business (Meta Business Manager), get a number, submit **utility templates** for renewal alerts, set up opt-in. | Templates need Meta approval; can't send WhatsApp alerts without it. | You (+ notifications agent) | 1–3 weeks | ☐ |
| 2 | **SMS DLT registration** — register entity + header (sender ID) + **content templates** on a DLT portal (Jio/Airtel/Vodafone/BSNL). Register as **transactional/service**. | Unregistered SMS is silently dropped. | You (+ notifications agent) | 1–2 weeks | ☐ |
| 3 | **Razorpay account** — sign up, complete **KYC/business verification**, enable Subscriptions, create Plans. Activation needs the legal pages (item 5) live. | No payments until activated. | You (+ billing agent) | 3–7 days | ☐ |
| 4 | **Decide plan pricing** (tiers + INR + limits) and free-tier-vs-paywall (DECISIONS Q6/Q8). | Blocks Razorpay plans, pricing page, entitlement map. | You | now | ☐ |
| 5 | **Legal pages drafted** — Privacy (DPDP), Terms, **Refund & Cancellation**, GST/billing. | Required for Razorpay activation + DPDP. (Use a lawyer to review.) | You (+ ui agent drafts) | 3–7 days | ☐ |
| 6 | **DPDP basics** — appoint a **Grievance Officer**, plan consent records + data-principal request flow. | Legal obligation as a Data Fiduciary (employee PII). | You | 1 week | ☐ |
| 7 | **Sub-processor DPAs** — sign Data Processing Agreements with **Supabase, Vercel, Razorpay, Anthropic, WhatsApp BSP, SMS/email vendors**. | DPDP cross-border + processor compliance. | You | 1–2 weeks | ☐ |

## 🟠 Set up the build/runtime accounts
| # | Item | Owner | Lead time | Done |
|---|------|-------|-----------|:---:|
| 8 | **Google OAuth** — Google Cloud project, OAuth consent screen (may need verification for production), client ID/secret. | You (+ auth agent) | 1–5 days | ☐ |
| 9 | **Supabase project** `hgopttbpoyvmlzgzyzio` — authenticate MCP (`claude /mcp`), enable extensions (pgvector, pg_cron), **PITR backups**, get the **pooler** connection string. | You + agents | 1 day | ☐ |
| 10 | **Vercel** — create project, connect the **GitHub repo** (github.com/rostanai/sVault) for auto-deploy, set env vars (Preview/Prod). | You (+ devops) | 1 day | ☐ |
| 11 | **Anthropic API key** for RAG + confirm **DPA / data handling** (PII to US). Decide embedding model + dimension (default 1536). | You (+ search agent) | 1–3 days | ☐ |
| 12 | **Email sending domain** — transactional provider (SES/Sendgrid/Resend) + **SPF/DKIM/DMARC** DNS records. | You (+ devops) | 1–3 days | ☐ |
| 13 | **Observability accounts** — Sentry (errors) + an uptime/status-page tool. | You (+ devops) | 1 day | ☐ |
| 14 | **Domain + DNS** for the app & marketing site (and email subdomain). | You | 1 day | ☐ |

## 🟡 Content / brand (for marketing site)
| # | Item | Owner | Done |
|---|------|-------|:---:|
| 15 | **Brand assets** — logo, colors, tagline ("never miss a renewal…"), product screenshots. | You (+ ui agent) | ☐ |
| 16 | **Social proof** — any early customers / logos / testimonials to feature. | You | ☐ |
| 17 | **Demo-booking tool** (Calendly-class) for the Book-a-demo page. | You | ☐ |

## Sequencing note
Items **1, 2, 7** (WhatsApp, SMS DLT, DPAs) have the longest external clocks — kick them off **today**.
Items **4 + 5** unblock **3** (Razorpay). Everything else can proceed alongside coding.
The dev team can build against **test/sandbox** modes (Razorpay test, WhatsApp test number) while approvals are pending.
