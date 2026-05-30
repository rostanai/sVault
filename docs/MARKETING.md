# sVault — Marketing Website Spec (public site)

> Modern, outcome-driven B2B SaaS site that showcases features and converts visitors to the 14-day trial.
> Next.js (App Router) on Vercel, SSG/SSR for SEO. Designed in Stitch. Owner: `ui-ux-designer`.

## Positioning (2026 best practice = outcome, not feature list)
Lead with the **transformation**: "Never miss an insurance renewal again." Show the product solving the
Excel pain in 3–5 seconds. Address the 4 above-the-fold questions: *Is this for me? Can it do what I need?
Is it worth it? Can I trust it?* Keep the nav minimal: **Product · Features · Pricing · Resources · [Start free trial]**.

## Site map — all pages
### Core
1. **Home / Landing** — hero + the full conversion narrative (sections below)
2. **Features (overview)** — all features grouped, each linking to a detail page
3. **Feature detail pages** (programmatic SEO; one per pillar):
   - Renewal Alert Engine (WhatsApp/SMS/Email/Telegram)
   - Policy & Document Vault
   - Dashboard & Analytics
   - AI "Ask sVault" (RAG)
   - Approval Workflows
   - Multi-company / Subsidiaries
   - Developer API & Integrations
4. **How it works** — 3–4 step flow (Import Excel → Get alerts → Stay covered)
5. **Pricing** — plan tiers + INR pricing, comparison table, FAQ, trial CTA (high-intent page)
6. **Solutions / Use cases** — by persona/industry (Manufacturing, Logistics/Fleet, Multi-entity groups, Finance/Admin teams)
7. **Comparisons** — sVault vs Excel; sVault vs generic reminder tools (SEO + decision-stage)
8. **Integrations** — Razorpay, WhatsApp, Supabase, calendar, API
9. **Security & Compliance** — DPDP, encryption, RLS, data residency (trust page — key for B2B India)

### Trust & content
10. **Customer stories / Case studies / Testimonials** — peer proof (dominant 2026 trust signal)
11. **Resources / Blog** — content hub: pillar pages + articles (renewal management, DPDP, insurance ops) for SEO
12. **About** — company, mission, team
13. **Contact / Book a demo** — form + calendar; demo for larger accounts
14. **FAQ**

### Conversion / app entry
15. **Start free trial / Sign up** (→ app, Google OAuth)
16. **Login** (→ app)
17. **Request demo** (sales-assist for Enterprise)

### Legal (required — Razorpay/payment-gateway onboarding mandates these in India)
18. **Privacy Policy** (DPDP-aligned)
19. **Terms of Service**
20. **Refund & Cancellation Policy**
21. **Pricing/GST & billing terms**
22. **Cookie Policy** / consent banner
23. **404 / 500** + sitemap.xml + robots.txt

## Landing page sections (in order)
1. **Hero** — outcome headline (<44 chars), subtext, **one primary CTA** ("Start free trial"), product visual/animation, trust strip ("trusted by N companies")
2. **Problem** — the Excel pain (missed renewals, scattered docs)
3. **Solution / value props** — 3–4 outcome cards
4. **Feature showcase** — real UI screenshots of dashboard, alerts, Ask sVault (progressive disclosure)
5. **How it works** — 3 steps
6. **Social proof** — logos, testimonials, metrics near CTAs
7. **Multi-channel alerts highlight** — the differentiator (WhatsApp/SMS/Email/Telegram)
8. **Security & compliance** — DPDP/encryption badges
9. **Pricing teaser** — tiers + "see full pricing"
10. **FAQ**
11. **Final CTA** — "Start your 14-day free trial — no card required"
12. **Footer** — full nav, legal links, contact, social

## Conversion & SEO standards (2026, verified)
- **Single primary CTA** focus (single-CTA pages convert ~13.5% vs 10.5% multi).
- **Outcome-driven storytelling** > feature lists; show transformation.
- **Real product screenshots**, not abstract art. 3D/micro-animations sparingly.
- **Peer proof**: name clients ("including X, Y") > generic counts.
- **Personalized CTAs** by segment where possible (202% lift cited).
- **SEO**: content hubs (pillar + cluster), comparison & use-case pages, fast Core Web Vitals (Vercel/SSG), schema.org, OG tags, sitemap.
- **Accessibility** (WCAG) + responsive + dark mode.
- Analytics + A/B testing hooks; cookie consent (DPDP).

## Tech
Next.js App Router (SSG/ISR for marketing pages) on Vercel · Tailwind v4 + shadcn/ui · MDX for blog ·
form → email/CRM + lead capture · designed in Stitch (project `projects/10530408406746453783`).
