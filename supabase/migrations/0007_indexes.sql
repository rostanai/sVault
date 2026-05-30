-- 0007 — Indexes (tenant/org scoping, RLS policy columns, search, vector)

-- Tenant/org scoping (every RLS policy filters on these)
create index idx_organizations_tenant   on public.organizations(tenant_id);
create index idx_organizations_parent    on public.organizations(parent_org_id);
create index idx_profiles_tenant_org     on public.profiles(tenant_id, org_id);
create index idx_providers_tenant         on public.providers(tenant_id);
create index idx_policies_tenant_org      on public.policies(tenant_id, org_id);
create index idx_policy_docs_tenant_org   on public.policy_documents(tenant_id, org_id);
create index idx_alerts_tenant            on public.alerts(tenant_id);
create index idx_alert_rules_tenant       on public.alert_rules(tenant_id);
create index idx_notif_tenant             on public.notification_log(tenant_id);
create index idx_approvals_tenant_org     on public.approvals(tenant_id, org_id);
create index idx_audit_tenant             on public.audit_log(tenant_id);
create index idx_chunks_tenant_org        on public.document_chunks(tenant_id, org_id);
create index idx_subscriptions_tenant     on public.subscriptions(tenant_id);
create index idx_invoices_tenant          on public.invoices(tenant_id);
create index idx_api_keys_tenant          on public.api_keys(tenant_id);

-- Hot query paths
create index idx_policies_expiry          on public.policies(expiry_date);
create index idx_policies_status          on public.policies(status);
create index idx_policies_owner           on public.policies(owner_id);
create index idx_policies_provider        on public.policies(provider_id);
create index idx_policies_category        on public.policies(category);
create index idx_alerts_schedule          on public.alerts(scheduled_for, status);
create index idx_approvals_status         on public.approvals(status);
create index idx_billing_events_eventid   on public.billing_events(event_id);
create index idx_api_keys_hash            on public.api_keys(key_hash);

-- Fuzzy / full-text search on policy title & number
create index idx_policies_title_trgm  on public.policies using gin (title gin_trgm_ops);
create index idx_policies_number_trgm on public.policies using gin (policy_number gin_trgm_ops);

-- Vector similarity (RAG) — HNSW cosine
create index idx_chunks_embedding on public.document_chunks
  using hnsw (embedding vector_cosine_ops);
