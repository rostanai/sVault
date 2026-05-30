-- 0012 — SECURITY FIX (security-auditor C1): billing-write privilege escalation
-- The generic tenant-write RLS loop in 0008 granted admin/manager FOR ALL on
-- subscriptions + invoices, letting a tenant self-upgrade their plan without payment.
-- Restrict billing writes to super-admin / service-role only; keep tenant SELECT.

drop policy if exists subscriptions_tenant_write on public.subscriptions;
drop policy if exists invoices_tenant_write on public.invoices;

create policy subscriptions_super_write on public.subscriptions
  for all using (public.is_super_admin()) with check (public.is_super_admin());
create policy invoices_super_write on public.invoices
  for all using (public.is_super_admin()) with check (public.is_super_admin());
