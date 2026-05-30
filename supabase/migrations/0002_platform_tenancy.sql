-- 0002 — Platform plane (plans, global config) + tenancy + org hierarchy + profiles

------------------------------------------------------------------------------
-- PLATFORM PLANE  (managed by Super Admin; above all tenants)
------------------------------------------------------------------------------
-- Subscription plan definitions (editable data, not hardcoded)
create table public.plans (
  id            uuid primary key default gen_random_uuid(),
  tier          plan_tier not null,
  name          text not null,
  description   text,
  price_inr     numeric(12,2) not null default 0,   -- monthly price in INR
  billing_period text not null default 'monthly',   -- monthly | annual
  is_active     boolean not null default true,
  -- entitlements: feature flags + numeric limits, e.g.
  -- {"features":{"rag":true,"sms":false,"api":false},"limits":{"policies":100,"users":3,"alerts_month":500}}
  entitlements  jsonb not null default '{}'::jsonb,
  razorpay_plan_id text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- Global config & secrets (AI keys, channel/Razorpay creds). Encrypted at app layer.
create table public.platform_settings (
  key           text primary key,                   -- e.g. 'claude_api_key','whatsapp','razorpay'
  value_encrypted text,                              -- ciphertext (never plaintext)
  is_secret     boolean not null default true,
  updated_by    uuid,                                -- auth.users id of super admin
  updated_at    timestamptz not null default now()
);

-- Platform-plane audit (super-admin actions: plan edits, secret changes, impersonation)
create table public.platform_audit_log (
  id            bigint generated always as identity primary key,
  actor         uuid,                                -- super admin auth.users id
  action        audit_action not null,
  target        text,
  detail        jsonb,
  created_at    timestamptz not null default now()
);

------------------------------------------------------------------------------
-- TENANT PLANE  (a tenant = a corporate group)
------------------------------------------------------------------------------
create table public.tenants (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  status        text not null default 'active',      -- active | suspended
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- Organization tree: parent company + subsidiaries within a tenant
create table public.organizations (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references public.tenants(id) on delete cascade,
  parent_org_id uuid references public.organizations(id) on delete restrict,
  name          text not null,
  org_type      org_type not null default 'parent',
  gstin         text,                                -- India GST number
  is_active     boolean not null default true,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- App users (1:1 with auth.users) + their tenant/org/role
create table public.profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  tenant_id     uuid references public.tenants(id) on delete cascade,
  org_id        uuid references public.organizations(id) on delete set null,
  role          tenant_role not null default 'viewer',
  full_name     text,
  email         text,
  phone         text,                                -- E.164 for WhatsApp/SMS
  is_active     boolean not null default true,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- Team invitations (invite by email -> link -> auto-join correct tenant/org)
create table public.invitations (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references public.tenants(id) on delete cascade,
  org_id        uuid references public.organizations(id) on delete set null,
  email         text not null,
  role          tenant_role not null default 'viewer',
  token         text not null unique,
  invited_by    uuid references public.profiles(id),
  accepted_at   timestamptz,
  expires_at    timestamptz not null default now() + interval '7 days',
  created_at    timestamptz not null default now()
);

------------------------------------------------------------------------------
-- ORG-HIERARCHY RLS HELPERS (depend on organizations)
------------------------------------------------------------------------------
-- All descendant org ids of a root (root included) — powers parent roll-up.
create or replace function public.descendant_org_ids(root uuid)
  returns setof uuid language sql stable as $$
  with recursive tree as (
    select id from public.organizations where id = root
    union all
    select o.id from public.organizations o
      join tree t on o.parent_org_id = t.id
  )
  select id from tree
$$;

-- Orgs the current user may access:
--   super admin -> none here (handled separately, full access)
--   admin/manager -> their org + all subsidiaries (roll-up)
--   owner/viewer  -> their own org only
create or replace function public.accessible_org_ids()
  returns setof uuid language sql stable as $$
  select case
    when public.jwt_role() in ('admin','manager')
      then o.id
    else case when o.id = public.jwt_org_id() then o.id end
  end
  from (
    select unnest(array(select public.descendant_org_ids(public.jwt_org_id()))) as id
  ) o
  where o.id is not null
$$;
