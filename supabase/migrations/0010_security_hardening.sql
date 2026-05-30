-- 0010 — Security hardening (from Supabase security advisor after 0001-0009)

-- Pin search_path on helper/trigger functions (fixes function_search_path_mutable).
alter function public.set_updated_at() set search_path = public, pg_catalog;
alter function public.jwt_tenant_id() set search_path = public, pg_catalog;
alter function public.jwt_org_id() set search_path = public, pg_catalog;
alter function public.jwt_role() set search_path = public, pg_catalog;
alter function public.is_super_admin() set search_path = public, pg_catalog;
alter function public.descendant_org_ids(uuid) set search_path = public, pg_catalog;
alter function public.accessible_org_ids() set search_path = public, pg_catalog;
alter function public.compute_policy_status() set search_path = public, pg_catalog;
alter function public.match_document_chunks(vector, integer) set search_path = public, pg_catalog;

-- Trigger-only SECURITY DEFINER functions must NOT be callable via PostgREST RPC.
revoke execute on function public.audit_row() from public, anon, authenticated;
revoke execute on function public.handle_new_user() from public, anon, authenticated;

-- NOTE (accepted): extension_in_public WARN for pg_trgm/unaccent/vector/btree_gin.
-- Moving them to an `extensions` schema would require recreating dependent indexes
-- (incl. the HNSW vector index); deferred as low-risk. Tracked in docs/CONSIDERATIONS.md.
