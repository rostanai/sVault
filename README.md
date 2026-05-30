# sVault

**Corporate Insurance Portfolio & Renewal Management System** — a multi-tenant B2B SaaS that replaces
manual Excel with a dashboard, document vault, **multi-channel renewal alerts** (WhatsApp/SMS/Email/Telegram),
and **AI "Ask sVault"** over policy documents. India-first (INR/GST, DLT, DPDP).

> 📚 Product & engineering docs live in [`docs/`](docs/) — start with `docs/PRD.md` and `docs/BUILD_PLAN.md`.
> 🤖 Built by a 12-agent Claude Code team (see `docs/TEAM.md` and `.claude/agents/`).

## Monorepo layout
```
backend/    FastAPI (Python 3.13, uv) REST/OpenAPI — Vercel serverless functions
frontend/   Next.js 16 + React 19 + Tailwind v4 + shadcn/ui — app + marketing site
supabase/   Postgres migrations (extensions, enums, tables, RLS, functions, triggers, publications)
docs/       PRD, build plan, schema, features, decisions, etc.
```

## Stack
FastAPI · Pydantic v2 · SQLAlchemy 2 · Supabase (Postgres + Auth + Storage + pgvector + pg_cron) ·
Next.js 16 / React 19 / Tailwind v4 / shadcn · Razorpay · Claude API (RAG) · **Vercel** (GitHub auto-deploy).

## Local development
### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # or: uv sync
cp .env.example .env             # fill Supabase pooler URL etc.
uvicorn app.main:app --reload    # http://localhost:8000  (docs at /docs)
pytest -q
```
### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev                      # http://localhost:3000
```

## Database (Supabase)
Migrations are in `supabase/migrations/`. Apply via the Supabase MCP (`apply_migration`) or the Supabase CLI.
Project ref: `hgopttbpoyvmlzgzyzio`. Use the **transaction pooler** connection string from serverless.

## Deployment (Vercel)
- **frontend/** → Vercel project (Next.js, auto-deploy on push; PR = preview, `main` = prod).
- **backend/** → Vercel project (Python; `backend/vercel.json` routes all to `api/index.py`).
- Point the frontend's `NEXT_PUBLIC_API_BASE` at the backend deployment.
- Scheduler (renewal alerts) runs via Supabase `pg_cron` / Vercel Cron hitting the dispatch endpoint.

## Status
**M0 — Foundation** (scaffold + health + error handling + CI). See `docs/BUILD_PLAN.md` for the roadmap.
