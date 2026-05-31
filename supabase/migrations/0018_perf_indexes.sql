-- 0018_perf_indexes.sql
-- Performance: composite indexes for hot (tenant_id, status) filter patterns and a
-- GIN full-text index for RAG / document-library search. From the pre-launch
-- performance audit (see docs/HANDOFFS.md). All idempotent (IF NOT EXISTS).

-- Notification bell feed: WHERE tenant_id = :t AND status IN (...) on alerts/approvals.
create index if not exists ix_alerts_tenant_status
  on public.alerts (tenant_id, status);

create index if not exists ix_approvals_tenant_status
  on public.approvals (tenant_id, status);

-- Dashboard expiry buckets: WHERE tenant_id = :t AND status IN (...) AND expiry_date BETWEEN ...
-- Partial (expiry_date not null) keeps the index small; covers the bucket COUNTs.
create index if not exists ix_policies_tenant_status_expiry
  on public.policies (tenant_id, status, expiry_date)
  where expiry_date is not null;

-- Ask sVault (RAG) + document library full-text search over chunk content.
-- Turns the sequential scan in rag_service._retrieve / document_library search into
-- an index scan. The 'english' regconfig makes to_tsvector immutable (index-safe).
create index if not exists ix_chunks_content_fts
  on public.document_chunks using gin (to_tsvector('english', content));
