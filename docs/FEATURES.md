# sVault — Full Feature Catalog

> Corporate Insurance Portfolio & Renewal Management System.
> Phase tags: 🟢 MVP · 🟡 Phase 1 · 🔵 Phase 2. Derived from PROJECT_BRIEF.md + RESEARCH.md.

## 1. Policy / Record Management
- 🟢 Create / edit / view / archive insurance policies
- 🟢 Policy fields: policy number, insurer/provider, internal owner (who finalized vendor), asset/description, sum insured, premium (INR), inception date, expiry date, renewal date, status
- 🟢 Asset/policy-type taxonomy: Vehicle, Machinery, Plant, Factory/Property, Employees (group health/GPA), Key-person, Stock (Raw Material / Finished Goods) — extensible
- 🟢 Auto-computed status: Active / Expiring Soon / Lapsed / Renewed / Cancelled
- 🟢 Days-to-expiry indicator + color coding
- 🟡 Sub-asset / line items under a policy (e.g. multiple vehicles in one fleet policy)
- 🟡 Policy linking (parent/renewal chain — last year's policy → this year's)
- 🟡 Custom fields per insurance category
- 🟡 Bulk import from existing Excel (migration) + export
- 🔵 Endorsements / mid-term amendments tracking
- 🔵 Co-insurance / multi-insurer split tracking

## 2. Dashboard & Analytics
- 🟢 Overview: total policies, total sum insured, total premium, counts by status
- 🟢 Upcoming expiries widget (next 30 / 60 / 90 days)
- 🟢 At-risk / lapsed policies highlight
- 🟢 Breakdown by category, by provider, by internal owner
- 🟡 Premium spend trends over time (charts)
- 🟡 Sum-insured by category / location
- 🟡 Renewal calendar view (month/quarter)
- 🟡 Owner workload view (policies per team member)
- 🔵 Cost analytics: premium vs sum insured ratios, YoY premium change
- 🔵 Provider performance (renewal turnaround, claim history)

## 3. Renewal Alert Engine ⭐ (core differentiator)
- 🟢 Configurable lead-time cadence (default 60 / 30 / 15 / 7 / 1 days before expiry)
- 🟢 Multi-channel dispatch: WhatsApp, Email, SMS, Telegram
- 🟢 Per-policy and global alert configuration
- 🟢 Daily scheduler that scans expiries and sends due alerts
- 🟢 Alert recipients: policy owner + configurable CC (manager/admin)
- 🟡 Escalation: if unacknowledged, escalate owner → manager → admin
- 🟡 Acknowledge / snooze / "mark renewed" from the alert or app
- 🟡 Quiet hours & channel priority/fallback (if WhatsApp fails → SMS → email)
- 🟡 Custom alert templates per channel
- 🔵 Smart cadence (ML-suggested timing based on past renewal lead times)
- 🔵 Two-way WhatsApp/Telegram replies (confirm renewal via chat)

## 4. Notification & Communication
- 🟢 WhatsApp Business API (utility/transactional template messages)
- 🟢 Email (SMTP/transactional provider) with attachments
- 🟢 SMS (India DLT-compliant: registered templates, brand name, transactional window)
- 🟢 Telegram bot delivery
- 🟢 Notification log: what was sent, to whom, channel, delivery status, timestamp
- 🟡 In-app notification center / bell
- 🟡 Delivery receipts & retry on failure
- 🟡 Per-user channel preferences & opt-in/opt-out
- 🔵 Push notifications (mobile/PWA)
- 🔵 Digest mode (daily/weekly summary instead of per-policy)

## 5. Document Management
- 🟢 Upload policy soft copies (PDF/image) per policy
- 🟢 Secure storage (encrypted at rest) + download
- 🟢 Document library, searchable, filter by policy/category
- 🟡 Document versioning (renewal supersedes prior copy, history kept)
- 🟡 OCR text extraction (search inside documents)
- 🟡 AI auto-extraction of key fields (expiry date, sum insured, policy no.) from uploaded PDF
- 🟡 Multiple document types per policy (schedule, endorsement, invoice, claim form)
- 🔵 Auto-classification of uploaded documents by type

## 6. Users, Roles & Permissions
- 🟢 User accounts + authentication (login, password reset, sessions)
- 🟢 Core roles: Admin, Manager, Owner/Team-member, Viewer
- 🟢 Function-level access (who can see/edit/delete what)
- 🟡 Object-level access (owners manage only their policies; managers see all)
- 🟡 Granular permission matrix (resource × action × role)
- 🟡 Teams / departments grouping
- 🔵 SSO (Google/Microsoft/SAML)
- 🔵 Multi-factor authentication (MFA)
- 🔵 Multi-tenant (multiple companies/orgs isolated) — if SaaS

## 7. Vendor / Provider Management
- 🟢 Provider directory (insurer name, contact, type)
- 🟢 Link policies to providers
- 🟡 Broker/agent details + relationship owner
- 🟡 Provider contact log (calls, emails)
- 🔵 Provider rating & renewal history
- 🔵 Provider portal (vendor uploads renewal quotes)

## 8. Financial Tracking
- 🟢 Premium amount (INR) per policy
- 🟢 GST capture on premium
- 🟡 Payment status (paid/pending/installments)
- 🟡 Installment / premium due reminders (separate from expiry)
- 🟡 Total premium outflow reports (monthly/quarterly/annual)
- 🔵 Budget vs actual premium tracking
- 🔵 Invoice/receipt storage & reconciliation

## 9. Search & Filtering
- 🟢 Search policies by number, provider, owner, asset, category
- 🟢 Filter by status, expiry window, category, owner
- 🟢 Sort by days-to-expiry, premium, sum insured
- 🟡 Full-text search inside uploaded documents (Postgres FTS)
- 🔵 Semantic / natural-language search (pgvector — "all factory fire policies expiring this quarter")

## 9A. AI / RAG Intelligence ⭐ ("Ask sVault")
> Retrieval-Augmented Generation over your own policy documents — answers are **grounded in the
> actual uploaded PDFs** (reduces hallucination), and retrieval is **permission-aware** (RLS-filtered,
> so users only get answers from policies they can access). Stack: Supabase **pgvector** + **Claude API**.
- 🟡 **Ask sVault** — natural-language Q&A over the portfolio ("which factory policies expire in Q3?", "what's the sum insured on the fleet policy?")
- 🟡 **Clause-level document Q&A** — ask about deductibles, exclusions, coverage limits in a specific policy; answer cites the source clause
- 🟡 **AI policy summarization** — auto-summary of a long policy PDF (coverage, sum insured, key dates, exclusions)
- 🟡 **AI field auto-extraction** — pull policy no., expiry, sum insured, premium from uploaded PDF on ingest (feeds OCR pipeline)
- 🟡 **Permission-aware semantic retrieval** — pgvector similarity filtered by RLS / a document-access join table
- 🔵 **Coverage gap & overlap analysis** — AI flags assets with no/expiring cover or duplicate coverage
- 🔵 **Renewal assistant** — AI drafts a renewal brief comparing this year vs last (premium delta, coverage changes)
- 🔵 **Provider/quote comparison** — AI compares competing renewal quotes side-by-side
- 🔵 **Hybrid search + rerank** — BM25 keyword + vector + cross-encoder rerank (beats pure vector)
- 🔵 **Contextual Retrieval ingestion** — Claude "situates" each document chunk with context before embedding for higher retrieval accuracy

## 10. Audit, Compliance & Security (DPDP)
- 🟢 Audit log (who changed what, when) — created/updated/deleted records
- 🟢 Encryption at rest for documents & sensitive fields
- 🟢 Role-based access control + RLS at database level
- 🟡 1-year audit-log retention (DPDP Rule 6)
- 🟡 Data export for a user / data-principal request (DPDP)
- 🟡 Breach-notification workflow hooks (DPDP Rule 7)
- 🟡 PII data-minimisation for employee group-health (policy-level vs member-level)
- 🔵 Consent management for personal data
- 🔵 Configurable data-retention & auto-purge policies

## 11. Reporting & Export
- 🟡 Renewal report (upcoming, lapsed, renewed) — PDF/Excel export
- 🟡 Portfolio report by category/owner/provider
- 🟡 Scheduled email reports (weekly renewal digest to management)
- 🔵 Custom report builder
- 🔵 Compliance/audit-ready report packs

## 12. Integrations
- 🟡 Calendar sync (Google/Outlook) — expiry dates as events
- 🔵 Accounting/ERP (Tally, Zoho, SAP) for premium/GST
- 🔵 Cloud storage import (Drive/SharePoint) for existing soft copies
- 🔵 Webhook/REST API for other internal systems
- 🔵 Slack / MS Teams alert channel

## 13. Claims (later)
- 🔵 Claims register linked to policies
- 🔵 Claim status tracking + document attachments
- 🔵 Claim history per asset/provider for renewal negotiation

## 14. Admin & Settings
- 🟢 Manage users, roles, providers, categories
- 🟢 Channel/integration credentials (WhatsApp, SMS, email, Telegram)
- 🟢 Alert cadence defaults
- 🟡 Branding (logo, company name in templates)
- 🟡 Audit/activity dashboard for admins
- 🔵 Feature flags / environment config UI

## 15. Platform / UX
- 🟢 Responsive web app (desktop + mobile browser)
- 🟢 Loading / empty / error states everywhere
- 🟡 Dark mode
- 🟡 Onboarding / Excel migration wizard
- 🔵 PWA / installable mobile app
- 🔵 Native mobile app
- 🔵 Multi-language (English + regional)

## 16. Subscription & Plans (SaaS monetization) ⭐
- 🟢 **Plan tiers** (Free / Starter / Professional / Enterprise) — each maps to a feature + limit set
- 🟢 **14-day free trial** started at sign-up (grants Pro-tier access), with trial countdown + T-3/T-1/expiry reminders
- 🟢 **Razorpay** payment integration — Plans + Subscriptions, UPI Autopay / eMandate / cards
- 🟢 Subscription lifecycle: subscribe, upgrade, downgrade, pause, cancel, resume
- 🟢 **Webhook-driven** billing state (subscription.activated/charged/cancelled, payment.failed) — signature-verified, idempotent
- 🟡 Billing portal: invoices, payment history, GST invoices, update payment method
- 🟡 Proration on upgrade/downgrade; coupons / discount codes
- 🟡 Dunning (smart retries + failed-payment emails) and grace period → restricted/read-only on lapse
- 🟡 Usage metering for limit-based plans (policies, users, alerts/month, storage)
- 🟢 **In-app subscription page** — shows all plans with INR costing, current plan, and **upgrade/downgrade anytime** (esp. from trial) with **Razorpay checkout** inline
- 🟢 In-app upgrade prompts when a user hits a plan gate ("upgrade to unlock")
- 🔵 Annual vs monthly pricing; add-ons (extra users, extra alert volume)
- 🔵 Self-serve public pricing page

### Draft plan → feature map (confirm pricing with user)
| Capability | Trial (14d) | Free | Starter | Professional | Enterprise |
|------------|:----------:|:----:|:-------:|:------------:|:----------:|
| Policies (limit) | unlimited | 10 | 100 | unlimited | unlimited |
| Users | 5 | 1 | 3 | 15 | unlimited |
| Email alerts | ✅ | ✅ | ✅ | ✅ | ✅ |
| WhatsApp alerts | ✅ | ❌ | ✅ | ✅ | ✅ |
| SMS (DLT) alerts | ✅ | ❌ | ❌ | ✅ | ✅ |
| Telegram alerts | ✅ | ❌ | ✅ | ✅ | ✅ |
| Document vault | ✅ | ✅ (limited) | ✅ | ✅ | ✅ |
| AI "Ask sVault" (RAG) | ✅ | ❌ | ❌ | ✅ | ✅ |
| Analytics/reports | ✅ | ❌ | basic | full | full |
| SSO / MFA | ✅ | ❌ | ❌ | MFA | SSO+MFA |
| API access | ❌ | ❌ | ❌ | ✅ | ✅ |
| Audit log / DPDP tools | ✅ | ❌ | ❌ | ✅ | ✅ |
| Priority support | — | — | — | email | dedicated |

## 17. Feature Gating / Entitlements (enforces §16)
- 🟢 **Entitlement layer** between billing and product runtime — evaluates plan + limits + usage + subscription state → allow / limit / deny
- 🟢 **Server-side enforcement** (FastAPI dep `require_entitlement` / `check_limit`) — security-sensitive, never trust the client
- 🟢 **Feature flags** per plan (on/off: RAG, SMS, SSO, API)
- 🟢 **Quantitative limits** per plan (max policies, users, documents, alerts/month) with usage counters
- 🟢 Plan → entitlements map (versioned config/table); Razorpay webhook updates tenant entitlement state
- 🟡 UI feature-gating: hide/disable + "upgrade to unlock" prompts (mirrors server rules)
- 🟡 Graceful limit handling (block at cap with clear upgrade CTA; grace on trial/payment lapse)
- 🔵 Per-tenant overrides / custom contracts (Enterprise)

## 18. Auth, Registration, Onboarding & Trial
- 🟢 **Google OAuth sign-in / sign-up** (one-click) + email/password
- 🟢 **Self-serve registration** → creates tenant (organization) + tenant-admin user; starts 14-day trial
- 🟢 Email verification (low-friction — don't block first value)
- 🟢 **Team invitations** — admin invites users by email → invite link → auto-join the correct tenant
- 🟢 Forgot/reset password; session management
- 🟡 **Onboarding wizard** — role/intent selection, quick setup, **Excel import**, add first policy, configure first alert (target first value in 2–5 min)
- 🟡 Onboarding checklist + progress; contextual product tour (progressive, not big-bang)
- 🟡 Day-2 activation nudge (behavioral-trigger emails > time-based) — highest-leverage retention point
- 🟡 Trial-conversion prompts; in-app "your trial ends in N days" banner
- 🔵 SSO (SAML/Microsoft) for Enterprise; SCIM user provisioning
- 🔵 Personalized activation paths by company size / use case

## 19. Organization Hierarchy — Parent ↔ Subsidiary ⭐
> A tenant is a **corporate group**: a **parent company** with **subsidiary companies** under it.
> Policies and users belong to a specific company in the tree.
- 🟢 Organization tree per tenant: parent company + subsidiaries (`parent_org_id` self-reference)
- 🟢 Policies, documents, users, providers scoped to a specific **company** within the group
- 🟢 **Parent-company admins** get a **roll-up view** across all subsidiaries; subsidiary users are scoped to their own company only
- 🟢 RLS + permissions are **tenant- AND org-scoped** (a subsidiary can't see siblings' data)
- 🟡 Per-subsidiary dashboards + **consolidated group dashboard** (total premium / sum insured across the group)
- 🟡 Cross-subsidiary / group-level reporting
- 🟡 Assign or move a policy between companies (with permission)
- 🟡 Manage the org tree (add/rename/deactivate subsidiaries) in admin
- 🔵 Multi-level hierarchy (sub-subsidiaries), per-subsidiary branding
- **Billing scope:** subscription at the **parent/group level** by default (one account covers subsidiaries) — confirm with user.

## 20. Approval Workflows ⭐
> Configurable approvals for key actions, routed by **role/permission**, with **self-approval** where allowed.
- 🟢 Approval required for configurable actions: **renewal**, new policy, vendor finalization, high-value premium
- 🟢 **Role/permission-based routing** — approver determined by role (e.g. Manager/Admin) and/or org hierarchy (subsidiary → parent)
- 🟢 **Self-approval** — roles holding the `approve:self` permission can approve their own actions (configurable per role/action)
- 🟢 States: draft → **pending approval** → approved / rejected (with reason) — fully **audit-logged**
- 🟢 **Pending-approval inbox/queue** + approval notifications (via notifications-engineer)
- 🟡 **Multi-level / threshold approval** (e.g. owner → manager → finance above an amount)
- 🟡 Reminders + escalation on stale pending approvals; **delegation** (approver on leave)
- 🔵 Conditional rules engine (auto-approve under threshold; require N approvers above)

## 21. Platform / Global Admin Console (Super Admin) ⭐
> **Super Admin = the SaaS platform owner**, a privilege tier ABOVE all tenants (not a tenant role).
> Separate admin console. All actions audit-logged; access restricted to platform staff.
- 🟢 **Super Admin role** above tenants; dedicated platform admin console (separate from the tenant app)
- 🟢 **Manage subscription plans & pricing** — create/edit tiers, INR prices, limits, the feature→plan entitlement map (drives §16/§17)
- 🟢 **Global config / environment** — manage **AI API keys (Claude)**, default **WhatsApp / SMS / Razorpay / email** credentials, model settings, and feature flags — stored **encrypted** (secrets store), Super-Admin-only, audit-logged
- 🟢 **Tenant management** — list/search tenants, view subscription status, **suspend / activate**, see usage
- 🟡 Platform analytics — MRR, active tenants, trials & conversion, usage by plan
- 🟡 Support **impersonation** (enter a tenant read-only for support, audit-logged)
- 🟡 Coupons/discounts, system announcements/banners
- 🔵 Multiple platform-staff roles; secret/key **rotation** UI; per-tenant contract overrides

## 22. Developer API & Third-Party Integration ⭐
> Lets external systems integrate with sVault. API access is a paid-plan entitlement (Pro/Enterprise).
- 🟢 **API key management** — issue / revoke **scoped API keys** per tenant for third-party integration
- 🟢 **Public REST API** (OpenAPI-documented) for policies, alerts, documents — API-key authenticated, tenant/org-scoped
- 🟢 **Scopes + rate limiting** per key; keys gated by plan entitlement (`feature:api`)
- 🟢 Keys stored hashed; show once on creation; last-used + revoke
- 🟡 **Outbound webhooks** — notify external systems on events (policy.created, renewal.due, approval.pending, payment.failed)
- 🟡 Per-key API usage logs & analytics
- 🔵 Developer portal + docs site; SDKs; OAuth2 client-credentials for partners

## 23. Marketing Website (public site) ⭐
> Modern, outcome-driven SaaS site to showcase features + convert to the 14-day trial. Full spec: `docs/MARKETING.md`.
- 🟢 **Home/landing** — hero (outcome headline + single CTA), problem→solution, feature showcase (real screenshots), how-it-works, social proof, multi-channel-alert highlight, security badges, pricing teaser, FAQ, final CTA, footer
- 🟢 **Pricing page** — plan tiers + INR costing, comparison table, trial CTA
- 🟢 **Features overview** + per-pillar **feature detail pages** (alerts, vault, dashboard, AI, approvals, multi-company, API)
- 🟢 **Legal pages** (required for Razorpay onboarding): Privacy (DPDP), Terms, Refund & Cancellation, GST/billing terms, Cookie consent
- 🟢 **Sign-up / Login / Start-free-trial** entry points (→ app, Google OAuth)
- 🟡 **Solutions/use-cases** (by industry/persona), **comparisons** (vs Excel / vs reminder tools)
- 🟡 **Security & Compliance** trust page · **About** · **Contact / Book a demo**
- 🟡 **Resources/Blog** content hub (pillar + cluster) with MDX, for SEO
- 🟡 SEO essentials: SSG/ISR, Core Web Vitals, schema.org, OG tags, sitemap/robots
- 🔵 Customer stories/case studies · A/B testing · personalized CTAs by segment · multi-language
