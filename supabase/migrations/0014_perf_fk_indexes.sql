-- 0014_perf_fk_indexes.sql
-- Performance: add covering indexes for foreign keys flagged by Supabase's
-- performance advisor (unindexed_foreign_keys). Every tenant/org-scoped query
-- filters or joins on these columns; without an index Postgres falls back to a
-- sequential scan and FK cascade checks are slow. All additive + idempotent.

-- alerts / alert engine
create index if not exists ix_alert_rules_policy_id        on public.alert_rules (policy_id);
create index if not exists ix_alerts_org_id                on public.alerts (org_id);
create index if not exists ix_alerts_acknowledged_by       on public.alerts (acknowledged_by);
create index if not exists ix_notification_log_alert_id    on public.notification_log (alert_id);
create index if not exists ix_notification_log_policy_id   on public.notification_log (policy_id);

-- approvals
create index if not exists ix_approvals_org_id             on public.approvals (org_id);
create index if not exists ix_approvals_requested_by       on public.approvals (requested_by);
create index if not exists ix_approvals_approver_id        on public.approvals (approver_id);

-- policies + documents (hottest paths)
create index if not exists ix_policies_org_id              on public.policies (org_id);
create index if not exists ix_policies_created_by          on public.policies (created_by);
create index if not exists ix_policies_prev_policy_id      on public.policies (prev_policy_id);
create index if not exists ix_policy_documents_policy_id   on public.policy_documents (policy_id);
create index if not exists ix_policy_documents_org_id      on public.policy_documents (org_id);
create index if not exists ix_policy_documents_uploaded_by on public.policy_documents (uploaded_by);

-- RAG chunks (retrieval is scoped by tenant/org/policy/document)
create index if not exists ix_document_chunks_policy_id    on public.document_chunks (policy_id);
create index if not exists ix_document_chunks_org_id       on public.document_chunks (org_id);
create index if not exists ix_document_chunks_document_id  on public.document_chunks (document_id);

-- tenancy / profiles / invitations
create index if not exists ix_profiles_org_id             on public.profiles (org_id);
create index if not exists ix_invitations_tenant_id        on public.invitations (tenant_id);
create index if not exists ix_invitations_org_id           on public.invitations (org_id);
create index if not exists ix_invitations_invited_by       on public.invitations (invited_by);

-- billing
create index if not exists ix_billing_events_tenant_id     on public.billing_events (tenant_id);
create index if not exists ix_invoices_subscription_id     on public.invoices (subscription_id);
create index if not exists ix_subscriptions_plan_id        on public.subscriptions (plan_id);

-- platform / api
create index if not exists ix_api_keys_created_by          on public.api_keys (created_by);
create index if not exists ix_webhooks_tenant_id           on public.webhooks (tenant_id);
