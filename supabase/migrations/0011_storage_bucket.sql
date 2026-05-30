-- 0011 — Storage bucket for policy documents (private; type/size limited)

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'policy-documents', 'policy-documents', false,
  20971520,  -- 20 MB
  array['application/pdf','image/png','image/jpeg','image/webp']
)
on conflict (id) do nothing;

-- storage.objects has RLS enabled by default with NO policies => deny-all to anon/
-- authenticated. The backend signs upload/download URLs with the service role
-- (bypasses RLS); private bucket + short-lived signed URLs are the security boundary.
-- Path convention: {tenant_id}/{policy_id}/{uuid}_{filename}.
