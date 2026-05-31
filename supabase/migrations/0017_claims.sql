-- 0017_claims.sql
-- Claims module: a claim register linked to policies + a per-claim event timeline.
-- RLS is enabled with NO policies → service-role backend only (API filters by
-- tenant/org + object-level owner scope, mirroring policy_service).

create table if not exists public.claims (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  org_id uuid references public.organizations(id) on delete cascade,
  policy_id uuid not null references public.policies(id) on delete cascade,
  claim_number text,
  status text not null default 'reported',   -- draft/reported/under_review/approved/rejected/settled/closed
  claim_amount_inr numeric(14,2),
  approved_amount_inr numeric(14,2),
  incident_date date,
  reported_date date default now(),
  description text,
  created_by uuid references public.profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists ix_claims_policy_id on public.claims(policy_id);
create index if not exists ix_claims_tenant_id on public.claims(tenant_id);
create index if not exists ix_claims_org_id on public.claims(org_id);
create index if not exists ix_claims_status on public.claims(status);
alter table public.claims enable row level security;

create table if not exists public.claim_events (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  claim_id uuid not null references public.claims(id) on delete cascade,
  event_type text not null default 'note',    -- status_change / note
  from_status text,
  to_status text,
  note text,
  created_by uuid references public.profiles(id),
  created_at timestamptz not null default now()
);
create index if not exists ix_claim_events_claim_id on public.claim_events(claim_id);
create index if not exists ix_claim_events_tenant_id on public.claim_events(tenant_id);
alter table public.claim_events enable row level security;
