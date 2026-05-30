# sVault — Deployment (Vercel + GitHub auto-deploy)

> GitHub ↔ Vercel is already connected, so deploys are automatic:
> **push to `main` → Production**, **open a PR → Preview deployment** (unique URL per PR).
> Because this is a **monorepo** (separate `frontend/` and `backend/`), set it up as **two Vercel projects**.

## One-time setup: two Vercel projects from the same repo

### Project A — `svault-frontend` (Next.js)
| Setting | Value |
|---|---|
| Repository | `rostanai/sVault` |
| **Root Directory** | `frontend` |
| Framework preset | Next.js (auto-detected) |
| Build command | `next build` (default) |
| Env vars | `NEXT_PUBLIC_API_BASE` = the backend project's URL + `/api/v1` · `NEXT_PUBLIC_SUPABASE_URL` · `NEXT_PUBLIC_SUPABASE_ANON_KEY` |

### Project B — `svault-backend` (FastAPI on Python)
| Setting | Value |
|---|---|
| Repository | `rostanai/sVault` (same repo) |
| **Root Directory** | `backend` |
| Framework preset | Other (uses `backend/vercel.json` → `api/index.py`) |
| Env vars | `DATABASE_URL` (Supabase **transaction pooler**, port 6543) · `SUPABASE_URL` · `SUPABASE_SERVICE_ROLE_KEY` · `SUPABASE_JWT_SECRET` · `ENV=prod` · (later: Razorpay/Anthropic/WhatsApp/SMS keys) |

> Set env vars per **Environment** (Preview vs Production) in each project's Settings → Environment Variables.
> The Supabase pooler string is in Supabase → Project Settings → Database → Connection string → **Transaction** pooler.

## How the automation works (nothing else to wire)
- **Every push to a branch with an open PR** → Vercel builds a **Preview** for both projects and comments the URLs on the PR.
- **Merge to `main`** → Vercel promotes to **Production**.
- **CI gate**: GitHub Actions (`.github/workflows/ci.yml`) runs lint+tests on every PR; keep "require status checks" on in branch protection so a red CI blocks merge (and thus blocks the prod deploy).

## Recommended branch protection (GitHub → Settings → Branches → `main`)
- Require a pull request before merging
- Require status checks to pass (`backend`, `frontend` CI jobs)
- (optional) Require review

## Scheduler (renewal alerts) — activate after backend deploy
The engine (M4) exposes `POST /api/v1/alerts/dispatch`, guarded by the `X-Cron-Secret`
header (`CRON_SECRET` env var). Serverless has no always-on worker, so trigger it daily.
**Option A — Supabase `pg_cron` + `pg_net`** (recommended; both already enabled/available):
```sql
-- run once the backend is deployed and CRON_SECRET is set (use a strong secret)
select cron.schedule(
  'svault-daily-alert-scan',
  '30 3 * * *',  -- 09:00 IST = 03:30 UTC
  $$ select net.http_post(
       url := 'https://<backend-project>.vercel.app/api/v1/alerts/dispatch',
       headers := jsonb_build_object('X-Cron-Secret', '<CRON_SECRET>')
     ); $$
);
```
**Option B — Vercel Cron**: add to `vercel.json` a cron hitting the same endpoint with the header.
The dispatch is idempotent (unique `policy,lead_day,channel`), so an occasional double-fire is safe.

> Channels run in **simulated** mode until their credentials are set (WhatsApp BSP / SMS DLT
> pending per `START_NOW.md`); `notification_log` records the intended sends meanwhile.

## Vercel MCP
Added (`claude mcp add --transport http vercel https://mcp.vercel.com`). After a restart, run `/mcp` → **vercel** → Authenticate. Then deployments/status can be inspected from here (and the `vercel:*` skills are available).

## Quick verify after first deploy
1. Backend: open `https://<backend-project>.vercel.app/api/v1/health` → `{"status":"ok"}`.
2. Frontend: open the frontend URL → the home page shows "Backend API status: ok".
