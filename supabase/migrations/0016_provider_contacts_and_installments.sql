-- 0016_provider_contacts_and_installments.sql
-- Wave 5: provider contact log + policy premium installments (payment tracking).
-- RLS is enabled with NO policies → only the service-role backend can read/write
-- (the API filters by tenant_id/org explicitly), matching the app's access model.

-- Provider contact log
create table if not exists public.provider_contacts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  provider_id uuid not null references public.providers(id) on delete cascade,
  kind text not null default 'note',          -- call / email / meeting / note
  subject text,
  note text,
  contacted_at timestamptz not null default now(),
  created_by uuid references public.profiles(id),
  created_at timestamptz not null default now()
);
create index if not exists ix_provider_contacts_provider_id on public.provider_contacts(provider_id);
create index if not exists ix_provider_contacts_tenant_id on public.provider_contacts(tenant_id);
alter table public.provider_contacts enable row level security;

-- Policy premium installments / payment tracking
create table if not exists public.policy_installments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  policy_id uuid not null references public.policies(id) on delete cascade,
  amount_inr numeric(14,2) not null,
  due_date date not null,
  status text not null default 'pending',      -- pending / paid
  paid_at timestamptz,
  note text,
  created_at timestamptz not null default now()
);
create index if not exists ix_policy_installments_policy_id on public.policy_installments(policy_id);
create index if not exists ix_policy_installments_tenant_id on public.policy_installments(tenant_id);
create index if not exists ix_policy_installments_due_date on public.policy_installments(due_date);
alter table public.policy_installments enable row level security;
