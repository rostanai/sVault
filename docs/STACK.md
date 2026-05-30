# sVault — Tech Stack Baseline (pinned May 2026)

> Single source of truth for versions. Every agent reads this. Update here, not in each agent.

## Backend (REST / OpenAPI)
| Thing | Version / choice | Notes |
|-------|------------------|-------|
| Language | **Python 3.13** (min 3.12) | modern runtime |
| Framework | **FastAPI 0.136.x** | OpenAPI 3.1 auto-docs |
| Validation | **Pydantic v2** (>=2.7) | Rust core, 5–50× faster than v1 |
| ORM | **SQLAlchemy 2.0** + optionally **SQLModel** | async engine |
| Migrations | **Alembic** | versioned schema |
| Package mgr | **uv** (>=0.11) | replaces pip/poetry; `pyproject.toml` + `uv.lock` |
| Server | **Gunicorn + Uvicorn workers** (uvloop/httptools) | `--reload` only in dev |
| Auth tokens | **JWT** (short expiry) + refresh | python-jose / pyjwt |

## Database
| Thing | Choice | Notes |
|-------|--------|-------|
| Engine | **Supabase Postgres** | also exposes Auth, Storage, Realtime |
| Access control | **Row Level Security (RLS)** | always ON for exposed tables |
| RLS perf | index every `auth.uid() = user_id` column | >100× on big tables |
| RLS safety | never use `user_metadata` in policies (user-editable); use `app_metadata`/JWT claims | |
| Grants | **explicit** — since 2026-05-30 new projects don't expose tables to Data API by default | |
| Vector search | **pgvector** + RLS-filtered similarity | |
| Service key | server-side only, bypasses RLS — never ship to client | |

## Frontend (UI/UX)
| Thing | Version / choice | Notes |
|-------|------------------|-------|
| Framework | **Next.js 16** (App Router) | React Server Components |
| UI lib | **React 19** (stable) | no more `forwardRef` |
| Styling | **Tailwind CSS v4** | colors in OKLCH |
| Components | **shadcn/ui** | `new-york` style; `sonner` for toasts; `data-slot` attrs |
| Design source | **Google Stitch** (MCP) | project `projects/10530408406746453783` |

## DevOps / Deployment
| Thing | Choice |
|-------|--------|
| Hosting | **Vercel** (dev/preview + production) |
| Auto-deploy | **GitHub → Vercel**: every PR = preview deploy, merge to `main` = production |
| Frontend | Next.js deploys natively on Vercel |
| Backend | FastAPI as **Vercel Python serverless functions** (ASGI) — stateless |
| Database | **Supabase** (managed Postgres + Auth + Storage) |
| Scheduler | **no always-on worker** (serverless) → use **Supabase `pg_cron`** (or Vercel Cron) to trigger the alert-dispatch endpoint |
| Migrations | **Supabase migrations** (`supabase/migrations/*.sql`) applied via Supabase MCP / CLI |
| Local dev | `vercel dev` + Supabase (local CLI or remote project) |
| Repo | github.com/rostanai/sVault |
| Supabase project | `hgopttbpoyvmlzgzyzio` (MCP: project-scoped) |

> ⚠️ **Serverless implication:** Vercel functions are stateless and time-limited. The renewal-alert
> scheduler and queue workers can't run as persistent processes — drive them with **pg_cron / Vercel Cron
> hitting an endpoint**, or **Supabase Edge Functions**. Heavy/long jobs may need a separate worker host.

## Security baseline
- OWASP API Security Top-10 (2023 ed., still current). BOLA ≈ 40% of API attacks.
- Enforce authz at **object level** (which rows) AND **function level** (which endpoints).
- JWT: short TTL, scoped claims, verify signature every request, no PII/secrets in payload.
- Secrets in env / GitHub Actions secrets (OIDC), never in code. `.claude.json` chmod 600.
