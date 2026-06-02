-- 0019_document_content_hash.sql
-- Duplicate-document detection: add a content_hash column to policy_documents and
-- a composite index for fast per-policy dedup lookups.
--
-- content_hash stores a hex SHA-256 of the file bytes, computed by the browser
-- before upload. Nullable so existing/legacy rows are unaffected. Dedup is enforced
-- in the service layer (not as a DB unique constraint) so deliberate re-versions can
-- still coexist if ever needed.

alter table public.policy_documents
  add column if not exists content_hash text;

-- "Does this policy already have a document with this hash?" — partial index keeps
-- it small and skips null hashes.
create index if not exists ix_policy_documents_tenant_policy_hash
  on public.policy_documents (tenant_id, policy_id, content_hash)
  where content_hash is not null;
