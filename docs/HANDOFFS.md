### 2026-05-31 — notifications-engineer — weekly renewal email digest

- Did: Built the weekly renewal email digest feature (3 new files + 1 test file).

New files:
  - `backend/app/schemas/digest.py`: `DigestSendMeResponse`, `DigestDispatchResponse` (Pydantic models).
  - `backend/app/services/digest_service.py`:
    - `build_digest_text(policies) -> str` — pure function; plain-text branded digest listing policies expiring within 30 days, sorted soonest-first; "No upcoming renewals / All clear!" when empty.
    - `async send_for_tenant(db, tenant_id, recipient_email) -> dict` — queries tenant-scoped policies expiring in ≤30 days, builds digest, calls the existing email adapter (`app.services.notifications.email.send`), returns `{sent, recipient, policies}`.
    - `async dispatch_all(db) -> dict` — iterates all active Tenant rows; for each resolves admin/owner Profile rows with a non-null email; calls `send_for_tenant` per recipient; swallows per-recipient errors; returns `{tenants, emails_sent}`.
  - `backend/app/api/v1/digests.py`:
    - `POST /digests/dispatch` — `dependencies=[Depends(verify_cron)]` (imported from `app.api.v1.alerts`); calls `dispatch_all`; returns `DigestDispatchResponse`.
    - `POST /digests/send-me` — `Depends(get_current_user)`; resolves email from JWT claim then Profile row fallback; calls `send_for_tenant`; returns `DigestSendMeResponse`.
  - `backend/tests/test_digests.py`: 10 tests — dispatch without cron secret → 404; send-me without token → 401; build_digest_text titles/days/sort/brand/empty; send_for_tenant sent=True + count; string tenant_id coercion.

router.py include lines (tech-lead to add to `app/api/v1/router.py`):
  - `from app.api.v1 import digests`
  - `api_router.include_router(digests.router)  # weekly email digest`

NOTE for devops-engineer: `POST /api/v1/digests/dispatch` must be scheduled weekly via pg_cron (e.g. `SELECT cron.schedule('weekly-digest', '0 8 * * 1', $$SELECT net.http_post(url := '...', headers := '{"X-Cron-Secret":"..."}', body := '{}')$$)`) or a Vercel Cron entry in `vercel.json` (`{"path": "/api/v1/digests/dispatch", "schedule": "0 8 * * 1"}`). The `X-Cron-Secret` env var must be set.

- NOT edited: `app/api/v1/router.py` (as instructed).
- Results: ruff clean on all new files; 376/376 tests pass (366 pre-existing + 10 new).

### 2026-05-31 — api-engineer — DPDP account data-export endpoint

- Built: `GET /account/export` — downloadable JSON attachment (`svault-data-export.json`) containing a tenant-scoped data snapshot for DPDP data-principal portability requests.
- Files created (NEW — nothing edited):
  - `backend/app/services/account_export_service.py` — `build_export(db, user) -> dict`; assembles 9 sections (tenant, organizations, profiles, providers, provider_contacts, policies, policy_documents, installments, approvals); one SQL query per table; COLLECTION_LIMIT=5000 cap with `_truncated` flag; UUIDs/Decimals/dates serialised as strings; `storage_path` and all secret fields excluded.
  - `backend/app/api/v1/account.py` — thin router, `APIRouter(prefix="/account", tags=["account"])`, `GET /export`; no business logic; returns `Response(media_type="application/json", headers={"Content-Disposition": "attachment; filename=\"svault-data-export.json\"", "Cache-Control": "no-store"})`.
  - `backend/tests/test_account_export.py` — 7 tests: 401 guard, top-level keys, UUID/Decimal/date→str, storage_path excluded, no-tenant empty result, truncation flag, org-scoping for owner role.
- router.py include lines (tech-lead to add):
  - `from app.api.v1 import account`
  - `api_router.include_router(account.router)  # DPDP data-export`
- Permission choice: `get_current_user` (no role restriction). All authenticated users have a DPDP portability right; org scoping is applied inside the service (admin/manager → full tenant; owner/viewer → own org for policies/documents).
- Results: ruff clean; 383/383 tests pass (7 new + 376 pre-existing).
