-- 0005 — Alerts/notifications, approvals, audit log, RAG embeddings

------------------------------------------------------------------------------
-- RENEWAL ALERT ENGINE
------------------------------------------------------------------------------
-- Per-policy (or default) alert configuration
create table public.alert_rules (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references public.tenants(id) on delete cascade,
  policy_id     uuid references public.policies(id) on delete cascade, -- null = tenant default
  lead_days     int[] not null default '{60,30,15,7,1}',
  channels      alert_channel[] not null default '{whatsapp,email}',
  escalate      boolean not null default true,
  is_active     boolean not null default true,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- Individual scheduled alerts (one per policy + lead_day + channel)
create table public.alerts (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references public.tenants(id) on delete cascade,
  org_id        uuid references public.organizations(id) on delete cascade,
  policy_id     uuid not null references public.policies(id) on delete cascade,
  channel       alert_channel not null,
  lead_day      int not null,
  scheduled_for date not null,
  status        alert_status not null default 'scheduled',
  acknowledged_by uuid references public.profiles(id),
  acknowledged_at timestamptz,
  created_at    timestamptz not null default now(),
  -- idempotency: never schedule the same alert twice
  unique (policy_id, lead_day, channel)
);

-- Delivery log (every send attempt across channels)
create table public.notification_log (
  id            bigint generated always as identity primary key,
  tenant_id     uuid not null references public.tenants(id) on delete cascade,
  alert_id      uuid references public.alerts(id) on delete set null,
  policy_id     uuid references public.policies(id) on delete set null,
  recipient     text,
  channel       alert_channel not null,
  template      text,
  status        text not null,                       -- queued | sent | delivered | failed
  provider_msg_id text,
  error         text,
  sent_at       timestamptz not null default now()
);

------------------------------------------------------------------------------
-- APPROVAL WORKFLOWS
------------------------------------------------------------------------------
create table public.approvals (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references public.tenants(id) on delete cascade,
  org_id        uuid references public.organizations(id) on delete cascade,
  action_type   approval_action not null,
  entity_type   text not null,                       -- e.g. 'policy'
  entity_id     uuid not null,
  amount_inr    numeric(14,2),                        -- for threshold routing
  status        approval_status not null default 'pending',
  requested_by  uuid references public.profiles(id),
  approver_id   uuid references public.profiles(id),
  is_self_approval boolean not null default false,
  reason        text,
  decided_at    timestamptz,
  created_at    timestamptz not null default now()
);

------------------------------------------------------------------------------
-- AUDIT LOG (tenant plane; 1-year retention per DPDP Rule 6)
------------------------------------------------------------------------------
create table public.audit_log (
  id            bigint generated always as identity primary key,
  tenant_id     uuid references public.tenants(id) on delete cascade,
  org_id        uuid,
  actor         uuid,
  action        audit_action not null,
  entity_type   text,
  entity_id     uuid,
  detail        jsonb,
  created_at    timestamptz not null default now()
);

------------------------------------------------------------------------------
-- RAG: document chunks + embeddings ("Ask sVault"), permission-aware
------------------------------------------------------------------------------
create table public.document_chunks (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references public.tenants(id) on delete cascade,
  org_id        uuid not null references public.organizations(id) on delete cascade,
  policy_id     uuid references public.policies(id) on delete cascade,
  document_id   uuid references public.policy_documents(id) on delete cascade,
  content       text not null,                       -- chunk text (+ contextual prefix)
  embedding     vector(1536),                        -- adjust dim to embedding model
  created_at    timestamptz not null default now()
);

-- RLS-aware similarity search: only returns chunks the caller can access.
create or replace function public.match_document_chunks(
  query_embedding vector(1536),
  match_count int default 8
) returns table (id uuid, policy_id uuid, content text, similarity float)
language sql stable as $$
  select c.id, c.policy_id, c.content,
         1 - (c.embedding <=> query_embedding) as similarity
  from public.document_chunks c
  where c.tenant_id = public.jwt_tenant_id()
    and (public.is_super_admin() or c.org_id in (select public.accessible_org_ids()))
  order by c.embedding <=> query_embedding
  limit match_count
$$;
