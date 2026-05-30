# sVault — Project Brief

> Source: user problem statement (2026-05-30). Feature details will be refined by the deep-research report.

## What is sVault?
**A Corporate Insurance Portfolio & Renewal Management System.** sVault is an internal-use web app
for a company to manage **its own** insurance policies (it does NOT sell insurance). It replaces the
manual Excel + scattered email/folder soft-copies that the company uses today. It is a single system
of record for every policy, with a dashboard, in-app document storage, and — most importantly —
**multi-channel renewal alerts (WhatsApp, Telegram, SMS, email)** so renewals are never missed.

### Core problem being solved
- All insurance data lives in **manual Excel**; soft copies are scattered across **email and folders**.
- The team **misses renewal deadlines** because nobody keeps the Excel open — they only learn of a
  renewal when the **vendor reminds them**. sVault makes the system proactively alert them instead.

## Insurance types (policy categories) to support
- **Vehicle** (motor / fleet)
- **Machinery**
- **Plant**
- **Factory / property**
- **Employees** (group health / group personal accident)
- **Key-person insurance**
- **Stock insurance** — Raw Material and Finished Goods
- (extensible — new categories can be added)

## Tenancy & organization model
- **Multi-tenant SaaS, high scale** — sold to many corporate groups.
- Each tenant is a **corporate group**: a **parent company** with **subsidiary companies** under it.
  Policies/users/documents belong to a specific company in the tree. Parent admins get a roll-up
  across subsidiaries; subsidiary users are scoped to their own company. Subscription is at the
  parent/group level by default.

## Core entities (data model seed)
- **Policy** — category (above), policy number, insured asset/description, sum insured, premium (INR),
  **insurance provider/vendor**, **internal owner** (team member who finalized the vendor),
  **start date**, **expiry date**, **renewal date**, status (active / expiring / lapsed / renewed).
- **Document** — uploaded soft copy (PDF/image) attached to a policy, with version history.
- **Provider/Vendor** — insurer/broker details, contact.
- **Internal user / team member** — who owns/finalized a policy.
- **Alert / Reminder** — scheduled notifications per policy (lead times + channels + escalation).
- **AuditLog** — who changed what, when.
- **Organization** — a company in the group tree (parent or subsidiary); `parent_org_id` self-ref.
- **Subscription / Plan** — tenant's plan, trial, entitlements, Razorpay state.
- **Approval** — request + state (pending/approved/rejected), approver, reason, linked action.

## Key flows / screens
1. **Dashboard** — policies by status, upcoming expiries (next 30/60/90 days), by category, by owner,
   total sum insured / premium, lapsed/at-risk count.
2. **Policy list** — filter/search by category, provider, owner, expiry window; sort by days-to-expiry.
3. **Policy detail** — all fields + attached documents + alert schedule + history.
4. **Add / edit policy** — capture all fields, upload soft copy.
5. **Renewal alerts config** — per-policy or global lead-time cadence (e.g. 60/30/15/7/1 days before
   expiry) and channels (WhatsApp / Telegram / SMS / email), with escalation to the owner/admin.
6. **Notifications log** — what was sent, to whom, on which channel, delivery status.
7. **Document library** — all uploaded soft copies, searchable.
8. **Admin** — users, roles, providers, categories, channel/integration settings.

## Renewal-alert engine (the differentiator)
- Schedule reminders at configurable lead times before **expiry/renewal** date.
- **Multi-channel**: WhatsApp Business API (template messages), Telegram bot, SMS (India DLT-compliant),
  email. Escalate if unacknowledged.
- Daily scheduler scans for upcoming expiries and dispatches due alerts; logs delivery status.

## Users & roles (initial)
- **Admin** — manage users, providers, categories, integrations; full access.
- **Manager** — view all policies + dashboard, configure alerts, manage renewals.
- **Owner / Team member** — manage the policies they own; receive alerts.
- **Viewer** — read-only dashboard/records.
_(Final matrix lives in `docs/PERMISSIONS.md`.)_

## Constraints / context
- **India-based**: INR currency, GST on premiums, WhatsApp Business API + SMS DLT compliance,
  IRDAI/insurance context, **DPDP Act** for PII (employee data) and document storage.
- **Web app** first (responsive); mobile later if needed.
- Multi-tenant? Likely **single-company, multi-user** initially (one org). Confirm if SaaS-multi-tenant.

## Out of scope (for now)
- Selling/quoting insurance, broker CRM, claims processing (possible later phase).

## Open questions for the user
- Single company only, or multi-tenant SaaS for several companies?
- Roughly how many policies / users? (affects scale decisions)
- Which channel is priority #1 for alerts (WhatsApp likely)?
- Do they want approval workflows for renewals, or just reminders?
