# sVault — Plan Entitlement Map

> Single source of truth for the plan -> entitlements mapping.
> Prices are INR/month (confirm exact pricing with user — DECISIONS Q6).
> Managed via Super Admin console (platform/plans CRUD) — NOT hardcoded.
> See FEATURES.md §16-17 and DECISIONS D10/D17.

## Plan Tiers

| Tier         | Price (INR/mo) | Billing       |
|--------------|---------------|---------------|
| Free         | 0             | N/A           |
| Starter      | TBD           | monthly       |
| Professional | TBD           | monthly       |
| Enterprise   | TBD (custom)  | monthly/annual|

## Feature Flags per Plan

| Feature           | Free | Starter | Professional | Enterprise | Trial (14d) |
|-------------------|:----:|:-------:|:------------:|:----------:|:-----------:|
| email_alerts      |  Y   |    Y    |      Y       |     Y      |      Y      |
| whatsapp_alerts   |  N   |    Y    |      Y       |     Y      |      Y      |
| sms_alerts        |  N   |    N    |      Y       |     Y      |      Y      |
| telegram_alerts   |  N   |    Y    |      Y       |     Y      |      Y      |
| rag               |  N   |    N    |      Y       |     Y      |      Y      |
| analytics         |  N   | basic   |    full      |    full    |    full     |
| sso               |  N   |    N    |      N       |     Y      |      Y      |
| mfa               |  N   |    N    |      Y       |     Y      |      Y      |
| api               |  N   |    N    |      Y       |     Y      |      N      |
| audit_log         |  N   |    N    |      Y       |     Y      |      Y      |
| document_vault    |  Y   |    Y    |      Y       |     Y      |      Y      |

Note: "analytics" is a boolean flag in the entitlements JSON (full/basic distinction
is handled by the frontend based on plan tier). "basic" plans map to `false` at the
feature level; the UI shows limited analytics.

## Quantitative Limits per Plan

| Limit           | Free | Starter | Professional | Enterprise | Trial (14d) |
|-----------------|:----:|:-------:|:------------:|:----------:|:-----------:|
| policies        |  10  |   100   |   unlimited  |  unlimited |  unlimited  |
| users           |   1  |     3   |      15      |  unlimited |      5      |
| alerts_month    | 200  |   500   |   unlimited  |  unlimited |  unlimited  |
| documents       |  20  |   200   |   unlimited  |  unlimited |  unlimited  |

> unlimited is stored as -1 in the entitlements JSON.
> `within_limit(entitlements, key, count)` returns True when limit == -1 (unlimited).

## Entitlement JSON shape (stored in `plans.entitlements` JSONB column)

```json
{
  "features": {
    "email_alerts": true,
    "whatsapp_alerts": false,
    "sms_alerts": false,
    "telegram_alerts": false,
    "rag": false,
    "analytics": false,
    "sso": false,
    "mfa": false,
    "api": false,
    "audit_log": false,
    "document_vault": true
  },
  "limits": {
    "policies": 10,
    "users": 1,
    "alerts_month": 200,
    "documents": 20
  }
}
```

## Trial

- 14-day trial starts at sign-up (see DECISIONS D12).
- Trial grants Pro-tier entitlements (`_PRO_ENTITLEMENTS` in `app/services/entitlements.py`).
- Subscription status = `trialing`; `trial_ends_at` tracks expiry.
- On trial expiry: status moves to `expired`; tenant falls back to Free defaults.
- T-3/T-1/expiry notifications sent by notifications-engineer.

## Subscription lifecycle and entitlement state transitions

| Subscription status | Entitlements applied      |
|---------------------|--------------------------|
| trialing            | Pro-tier defaults         |
| active              | plan.entitlements         |
| past_due            | plan.entitlements (grace) |
| paused              | plan.entitlements         |
| cancelled           | Free defaults             |
| expired             | Free defaults             |
| (no subscription)   | Free defaults             |

## Server-side enforcement

All gated actions call into `app/services/entitlements.py`:

- `feature_allowed(entitlements, feature)` — pure, no DB.
- `within_limit(entitlements, key, count)` — pure, no DB.
- `await has_feature(db, tenant_id, feature)` — DB-backed.
- `await check_limit(db, tenant_id, key, current_count)` — DB-backed.
- `require_entitlement("feature_name")` — FastAPI dependency factory returning 403 if denied.

## Razorpay integration

- Each plan row has an optional `razorpay_plan_id` (set via Super Admin console).
- `POST /billing/subscribe` creates a Razorpay Subscription under the plan's Razorpay Plan.
- Webhook events (`subscription.activated/charged/cancelled`, `payment.failed`) update
  `subscriptions.status` via `handle_webhook` (idempotent on `billing_events.event_id`).
- Signature verification: HMAC-SHA256 of the raw body with `RAZORPAY_WEBHOOK_SECRET`.
