-- 0003 — Billing: subscriptions, invoices, payments (Razorpay), API keys, webhooks

-- One subscription per tenant (group-level billing by default)
create table public.subscriptions (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references public.tenants(id) on delete cascade,
  plan_id         uuid references public.plans(id),
  status          subscription_status not null default 'trialing',
  trial_ends_at   timestamptz,
  current_period_start timestamptz,
  current_period_end   timestamptz,
  cancel_at_period_end boolean not null default false,
  razorpay_customer_id     text,
  razorpay_subscription_id text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (tenant_id)
);

-- Invoices / payment records (mirrors Razorpay; GST-aware)
create table public.invoices (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references public.tenants(id) on delete cascade,
  subscription_id uuid references public.subscriptions(id) on delete set null,
  amount_inr      numeric(12,2) not null,
  gst_inr         numeric(12,2) not null default 0,
  status          text not null default 'created',  -- created | paid | failed | refunded
  razorpay_invoice_id text,
  razorpay_payment_id text,
  issued_at       timestamptz not null default now(),
  paid_at         timestamptz,
  pdf_url         text
);

-- Razorpay webhook events (idempotent processing)
create table public.billing_events (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid references public.tenants(id) on delete cascade,
  event_id        text unique,                       -- Razorpay event id (idempotency)
  event_type      text not null,                     -- subscription.activated, payment.failed, ...
  payload         jsonb not null,
  processed       boolean not null default false,
  received_at     timestamptz not null default now()
);

-- Scoped API keys for third-party integration (hashed; shown once)
create table public.api_keys (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references public.tenants(id) on delete cascade,
  name            text not null,
  key_prefix      text not null,                     -- visible prefix e.g. 'svk_live_ab12'
  key_hash        text not null,                     -- sha-256 of full key
  scopes          text[] not null default '{}',      -- e.g. {'policies:read','alerts:read'}
  rate_limit_per_min int not null default 60,
  last_used_at    timestamptz,
  revoked_at      timestamptz,
  created_by      uuid references public.profiles(id),
  created_at      timestamptz not null default now()
);

-- Outbound webhooks to external systems (signed payloads)
create table public.webhooks (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references public.tenants(id) on delete cascade,
  url             text not null,
  events          text[] not null default '{}',      -- policy.created, renewal.due, ...
  secret          text not null,                      -- HMAC signing secret
  is_active       boolean not null default true,
  created_at      timestamptz not null default now()
);
