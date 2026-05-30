# sVault — Error Handling & Debugging Standard

> How the whole stack reports, logs, recovers from, and lets us debug failures. All agents follow this.
> Principles: **fail safe, never leak internals, every error traceable (request_id), degrade gracefully.**

## 1. Backend error model (FastAPI)
- **Consistent envelope** on every error:
  ```json
  { "error": { "code": "entitlement_required", "message": "Your plan doesn't include SMS alerts",
               "details": {...}, "request_id": "req_abc123" } }
  ```
- **Error-code taxonomy** (stable, client-readable): `validation_error` (422), `unauthorized` (401),
  `forbidden` (403), `not_found` (404), `conflict` (409), `rate_limited` (429),
  `entitlement_required` / `payment_required` (402/403), `upstream_error` (502), `internal_error` (500).
- **Global exception handlers**: map `HTTPException` + `RequestValidationError` to the envelope; catch-all
  for unhandled → generic **500 with request_id**, full stack trace logged server-side only.
- **Never leak** stack traces, SQL, or secrets to clients.
- **Tenant safety**: for cross-tenant / cross-org / non-owned object access return **404, not 403**
  (don't reveal that an id exists). 403 only for known-but-forbidden actions within scope.
- **Request/correlation ID**: middleware assigns `X-Request-ID`, echoes it in the response + every log line + Sentry event so one id traces a request end-to-end.
- **Idempotency**: mutation + webhook endpoints accept/enforce idempotency keys (no double-charge / double-send).

## 2. External-service resilience (the failure-prone edges)
- **Timeouts + retries with backoff + circuit breakers** around every external call: Supabase, Razorpay, WhatsApp/SMS/email, Claude API.
- **Notifications**: on send failure → **channel fallback** (WhatsApp → SMS → email), retry with backoff, record status in `notification_log`, and a **dead-letter** path; alert ops on repeated failures.
- **Billing**: Razorpay webhooks are **idempotent** (dedupe on event id), retried, and **reconciled** (poll if a webhook is missed); `payment.failed` → dunning, not a crash.
- **RAG/LLM**: timeouts + token/rate-limit handling + **prompt caching**; on failure return a graceful "couldn't answer from your documents" — never a stack trace, never a hallucinated answer.
- **Storage**: handle partial/failed uploads, clean up orphans, validate before commit.

## 3. Frontend error handling (Next.js / React)
- **Error boundaries** per route (`error.tsx`) + global fallback + `not-found.tsx`. No white screen.
- Typed API client maps the **error envelope → friendly messages** (sonner toasts / inline field errors); show the **request_id** for support, never raw internals.
- **Loading / empty / error** states on every data view (already a UX standard).
- **Retry affordance** for transient errors; optimistic UI rolls back on failure; offline/timeout handling.
- Form validation mirrors backend rules; surface 422 `details` at field level.

## 4. Debugging & observability
- **Structured JSON logs** with `level, request_id, tenant_id, user_id, route` — **never PII/secrets**. Log levels per env (debug in dev, info/warn/error in prod).
- **Sentry** on frontend + backend: breadcrumbs, release tracking, **source maps** (frontend), grouped by error-code; tie events to `request_id`.
- **Trace a request**: one `request_id` correlates API logs ↔ Sentry ↔ frontend.
- **Platform logs**: Vercel function logs + Supabase logs/Query Insights + DB pool metrics.
- **Replayability**: failed alerts/webhooks land in a dead-letter table with payload → a **replay** script/endpoint (super-admin) to reprocess.
- **Health**: `/health` (liveness) + `/ready` (DB check). **Dashboards + alerting** on error-rate spikes, webhook failures, alert-dispatch failures, pool saturation.
- **Local dev**: `DEBUG` flag, verbose logging, seeded multi-tenant fixture, scripts to replay a webhook / trigger the alert scan locally.

## 5. Ownership
- Backend envelope, handlers, request-id, idempotency, upstream resilience → **api-engineer** (+ billing/notifications/search for their edges).
- Frontend boundaries + error UX → **ui-ux-designer**.
- Logging, Sentry, dashboards, alerting, dead-letter infra → **devops-engineer**.
- Negative/error-path + resilience tests → **qa-test-engineer**.
- Confirm no internal/PII leakage in errors or logs → **security-auditor**.
