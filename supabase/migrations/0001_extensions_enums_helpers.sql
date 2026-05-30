-- 0001 — Extensions, enumerated types, and RLS helper functions
-- sVault: multi-tenant insurance portfolio SaaS (platform + tenant planes, org hierarchy)

------------------------------------------------------------------------------
-- EXTENSIONS
------------------------------------------------------------------------------
create extension if not exists pgcrypto;      -- gen_random_uuid(), digest()
create extension if not exists pg_trgm;       -- fuzzy / trigram text search
create extension if not exists unaccent;      -- accent-insensitive search
create extension if not exists vector;        -- pgvector — RAG embeddings
create extension if not exists btree_gin;     -- composite GIN indexes
-- pg_cron drives the serverless renewal-alert scheduler.
-- On Supabase enable it once (Dashboard → Database → Extensions, or):
create extension if not exists pg_cron;

------------------------------------------------------------------------------
-- ENUMERATED TYPES
------------------------------------------------------------------------------
create type policy_category as enum (
  'vehicle','machinery','plant','factory_property',
  'employees_group_health','key_person',
  'stock_raw_material','stock_finished_goods','other'
);

create type policy_status as enum (
  'draft','pending_approval','active','expiring','lapsed','renewed','cancelled'
);

create type org_type        as enum ('parent','subsidiary');
create type tenant_role      as enum ('admin','manager','owner','viewer');  -- tenant plane
create type alert_channel    as enum ('whatsapp','email','sms','telegram');
create type alert_status     as enum ('scheduled','sent','delivered','failed','acknowledged','snoozed','cancelled');
create type plan_tier        as enum ('free','starter','professional','enterprise');
create type subscription_status as enum ('trialing','active','past_due','paused','cancelled','expired');
create type approval_status  as enum ('pending','approved','rejected','cancelled');
create type approval_action  as enum ('renewal','new_policy','vendor_finalization','high_value_premium','other');
create type document_type    as enum ('policy','schedule','endorsement','invoice','claim','other');
create type audit_action     as enum ('create','update','delete','login','logout','approve','reject','export','impersonate');

------------------------------------------------------------------------------
-- JWT CLAIM HELPERS  (claims set into app_metadata via a Supabase Auth hook)
-- Read identity/role from the verified JWT — never from user-editable metadata.
------------------------------------------------------------------------------
create or replace function public.jwt_tenant_id() returns uuid
  language sql stable as $$
  select nullif(auth.jwt() -> 'app_metadata' ->> 'tenant_id','')::uuid
$$;

create or replace function public.jwt_org_id() returns uuid
  language sql stable as $$
  select nullif(auth.jwt() -> 'app_metadata' ->> 'org_id','')::uuid
$$;

create or replace function public.jwt_role() returns text
  language sql stable as $$
  select coalesce(auth.jwt() -> 'app_metadata' ->> 'role','')
$$;

create or replace function public.is_super_admin() returns boolean
  language sql stable as $$
  select coalesce((auth.jwt() -> 'app_metadata' ->> 'is_platform_admin')::boolean, false)
$$;

-- Recursive descendants of an org (the org itself + all subsidiaries below it).
-- Defined after organizations table exists — see 0002. Declared here as a forward note.
