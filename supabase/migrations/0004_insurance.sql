-- 0004 — Insurance domain: providers, policies, documents

-- Insurers / brokers / vendors
create table public.providers (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references public.tenants(id) on delete cascade,
  name          text not null,
  contact_name  text,
  contact_email text,
  contact_phone text,
  notes         text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- Policies — the core record
create table public.policies (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references public.tenants(id) on delete cascade,
  org_id          uuid not null references public.organizations(id) on delete restrict,
  category        policy_category not null,
  policy_number   text,
  title           text not null,                     -- asset / description
  provider_id     uuid references public.providers(id) on delete set null,
  owner_id        uuid references public.profiles(id) on delete set null, -- who finalized the vendor
  sum_insured_inr numeric(14,2),
  premium_inr     numeric(14,2),
  gst_inr         numeric(14,2) default 0,
  inception_date  date,
  expiry_date     date,
  renewal_date    date,
  status          policy_status not null default 'active',
  prev_policy_id  uuid references public.policies(id) on delete set null, -- renewal chain
  custom_fields   jsonb not null default '{}'::jsonb,
  created_by      uuid references public.profiles(id),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

-- Uploaded policy soft copies (stored in Supabase Storage; row holds metadata + path)
create table public.policy_documents (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references public.tenants(id) on delete cascade,
  org_id        uuid not null references public.organizations(id) on delete restrict,
  policy_id     uuid not null references public.policies(id) on delete cascade,
  doc_type      document_type not null default 'policy',
  storage_path  text not null,                       -- Supabase Storage object path
  file_name     text not null,
  mime_type     text,
  size_bytes    bigint,
  version       int not null default 1,
  extracted     jsonb,                               -- OCR/AI-extracted fields
  uploaded_by   uuid references public.profiles(id),
  created_at    timestamptz not null default now()
);
