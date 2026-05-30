# sVault — Market & Product Research (verified)

> Deep-research report, 2026-05-30. 22 sources, 25 claims adversarially verified (24 confirmed, 1 refuted).
> Confidence labels are from 3-vote verification. Competitor features are from vendor pages (self-reported).

## 1. The problem is real and quantifiable  _(medium confidence)_
- Poor contract/renewal management can erode **up to ~9% of annual revenue** (WorldCC/IACCM, repurposed via blogs — dated origin).
- **~46%** of contracting professionals sometimes **can't locate a contract** (CLOC/DocuSign, n=1,300). Mirrors the "soft copies scattered in email/folders" pain.
- **Excel lacks** native workflow engines, trigger-based reminders, escalation, and audit trails. Bolt-ons (VBA, Power Automate) don't provide true escalation/audit. → validates replacing Excel.

## 2. Competitive landscape — adjacent, no direct hit (a real gap)  _(high confidence)_
| Product | Category | Target user | Relevance | Notable features |
|---------|----------|-------------|-----------|------------------|
| **TrustLayer** | COI compliance tracker | US/Canada risk/procurement teams | Partial — tracks **suppliers'** COIs, not own portfolio | AI reads COIs vs standards, color-coded status, renewal reminders, escalation (Plus) |
| **Certificial** | Real-time COI network | US/Canada procurement | Partial — third-party coverage monitoring | "Smart COI Network," 25k+ agencies (self-reported) |
| **Insuraa** (India) | Agent/broker CRM | Agents, brokers, advisors | India alert pattern, but manages **clients'** policies | Auto **WhatsApp + email + SMS** renewal reminders at **30/15/7 days** |
| **InsureBook** (India) | Agency management | Brokers/agencies | Same — client policies, not own | Upcoming-expiry tracking, SMS module, auto renewal reminders |
| **Remindax** | Generic expiry tracker | Any business | **Closest match** | Tracks insurance docs; multi-channel (email/SMS/WhatsApp/Slack); document vault |
| **ExpiryEdge** | Insurance renewal tracker | Any business | **Closest match** | Configurable **90/60/30/14-day** reminders via Email/SMS/WhatsApp; per-policy **document vault** |

**Key insight:** No identified product targets *an enterprise managing its OWN multi-line insurance portfolio* (vehicle + machinery + plant + factory + employee + key-person + stock). The closest tools (Remindax, ExpiryEdge) are generic expiry trackers. **→ Genuine product gap; a tailored internal tool is justified.** No public pricing was confirmed for any competitor.

## 3. Feature blueprint
**MVP must-haves** (validated against comparables):
- Central **multi-line policy record store** with the asset-type taxonomy.
- **Renewal dashboard** with color-coded status (active / expiring / lapsed).
- **In-app document upload / vault** (per-policy attachments).
- **Escalating multi-channel alert engine** (WhatsApp / SMS / email / Telegram) at configurable lead times.

**Later phases:** OCR/auto-extraction of expiry dates from uploaded policies, document **versioning**, granular **roles/permissions**, **audit trail**, **analytics/reporting**, **integrations** (accounting/ERP, calendar, SSO).

## 4. Alert architecture — India delivery compliance  _(high confidence)_
- **SMS = TRAI DLT regime.** Registration **mandatory**; unregistered SMS silently dropped (since Feb 2021).
  - **Transactional/Service** messages (renewal alerts likely qualify) → **no DND, 24/7** delivery.
  - **Promotional** → only **10:00–21:00 IST** (dropped outside window, not queued).
  - Every **content template** must carry the **brand name**; templates register **free**; variables tagged by data type; **CTA URLs/app links must be pre-whitelisted** (Aug/Oct 2024 rules).
- **WhatsApp Business API** → template messages; **open question:** whether renewal reminders classify as **"utility"** vs **"marketing"** (affects Meta pricing + opt-in).
- **Telegram bot** → cheap/free but **open question** whether reliable enough as a *primary* vs supplementary channel.
- **Recommended cadence:** **60 / 30 / 15 / 7 / 1 days** before expiry, with **escalation** to owner → manager/admin if unacknowledged. (Design choice synthesized from comparables; medium confidence.)

## 5. Compliance & security — India DPDP  _(high confidence)_
- App stores policy docs + **employee group-health/GPA PII** → it is a **Data Fiduciary** under **DPDP Act 2023 + DPDP Rules 2025** (notified **Nov 13, 2025**; phased deadlines ~Nov 2026 / May 2027).
- **Rule 6** — seven security controls: **encryption/masking/tokenisation**, access control, logging/monitoring, backups, **one-year log + data retention**, processor contracts, technical/org measures.
- **Rule 7** — **dual breach notification** to the Data Protection Board *and* affected individuals "without delay." Penalties up to **₹200 crore**.
- **IRDAI:** likely **no direct** obligation on a non-insurer merely storing its own policies — but DPDP applies fully. (Open question — verify.)
- **Design implication:** encrypt documents at rest, strict RLS/access control, audit logging with 1-yr retention, consider **data-minimising** employee PII (store policy-level data, not individual member records, where possible).

## 6. Recommended roadmap
- **Phase 0 (MVP):** policy CRUD + taxonomy, dashboard, document upload/vault, multi-channel alert engine (start **WhatsApp + email**, add SMS-DLT + Telegram), users + basic roles, audit log, encryption at rest.
- **Phase 1:** OCR auto-extraction of expiry/sum-insured, document versioning, granular RBAC, reporting/analytics (premium spend, sum-insured by category), escalation workflows.
- **Phase 2:** renewal approval workflows, vendor/provider portal, calendar/ERP/SSO integrations, mobile app, advanced DPDP tooling (consent, data-principal requests).

## Open questions (carried forward)
1. Pricing of Remindax/ExpiryEdge vs custom build — buy-vs-build check.
2. WhatsApp template classification (utility vs marketing) + Telegram reliability as primary channel.
3. IRDAI obligations for a non-insurer storing own policies (likely none — confirm).
4. Whether to data-minimise/segregate employee group-health PII to cut DPDP exposure.

## Refuted (excluded)
- "33% manually track / 9% don't track / 92% human error" — **refuted 0-3**, not used.

### Sources (verified subset)
TrustLayer, Certificial, Insuraa, InsureBook, Remindax, ExpiryEdge (vendor pages); messagecentral (TRAI DLT); Seclore, Mondaq, EY (DPDP). Full list with quality ratings in the research transcript.
