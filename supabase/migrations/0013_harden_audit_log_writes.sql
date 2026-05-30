-- 0013 — Harden append-only / service-only tables (security re-review follow-up).
-- audit_log must be tamper-resistant (DPDP); billing_events is webhook/service data.
-- The audit_row trigger is SECURITY DEFINER so it still inserts regardless of RLS;
-- this only removes DIRECT tenant write access. Admin reads unchanged.
drop policy if exists audit_log_tenant_write on public.audit_log;
drop policy if exists billing_events_tenant_write on public.billing_events;

create policy audit_log_super_write on public.audit_log
  for all using (public.is_super_admin()) with check (public.is_super_admin());
create policy billing_events_super_write on public.billing_events
  for all using (public.is_super_admin()) with check (public.is_super_admin());
