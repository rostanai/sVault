-- 0008 — Row Level Security: enable + policies (two planes, org-scoped)

-- Enable RLS everywhere
do $$
declare t text;
begin
  foreach t in array array[
    'plans','platform_settings','platform_audit_log',
    'tenants','organizations','profiles','invitations',
    'subscriptions','invoices','billing_events','api_keys','webhooks',
    'providers','policies','policy_documents',
    'alert_rules','alerts','notification_log','approvals','audit_log','document_chunks'
  ] loop
    execute format('alter table public.%I enable row level security;', t);
  end loop;
end $$;

------------------------------------------------------------------------------
-- PLATFORM PLANE — Super Admin only
------------------------------------------------------------------------------
create policy super_admin_all_plans on public.plans
  for all using (public.is_super_admin()) with check (public.is_super_admin());
-- plans are also READ-only to authenticated users (to render the pricing page)
create policy read_active_plans on public.plans
  for select using (is_active = true);

create policy super_admin_settings on public.platform_settings
  for all using (public.is_super_admin()) with check (public.is_super_admin());
create policy super_admin_pal on public.platform_audit_log
  for all using (public.is_super_admin()) with check (public.is_super_admin());

------------------------------------------------------------------------------
-- TENANT PLANE — tenant + org scoped. Super admin bypasses (full access).
-- Reusable predicate: row belongs to my tenant AND (super admin OR my accessible orgs)
------------------------------------------------------------------------------
-- tenants: a user sees only their own tenant; super admin sees all
create policy tenant_self on public.tenants
  for select using (public.is_super_admin() or id = public.jwt_tenant_id());
create policy tenant_super_write on public.tenants
  for all using (public.is_super_admin()) with check (public.is_super_admin());

-- organizations: same tenant; access limited to accessible orgs (roll-up)
create policy org_read on public.organizations
  for select using (
    public.is_super_admin()
    or (tenant_id = public.jwt_tenant_id()
        and (public.jwt_role() in ('admin','manager') or id = public.jwt_org_id()))
  );
create policy org_admin_write on public.organizations
  for all using (
    public.is_super_admin()
    or (tenant_id = public.jwt_tenant_id() and public.jwt_role() = 'admin')
  ) with check (
    public.is_super_admin()
    or (tenant_id = public.jwt_tenant_id() and public.jwt_role() = 'admin')
  );

-- profiles: see members of my tenant; manage self; admin manages tenant users
create policy profiles_read on public.profiles
  for select using (public.is_super_admin() or tenant_id = public.jwt_tenant_id());
create policy profiles_self_update on public.profiles
  for update using (id = auth.uid()) with check (id = auth.uid());
create policy profiles_admin on public.profiles
  for all using (
    public.is_super_admin()
    or (tenant_id = public.jwt_tenant_id() and public.jwt_role() = 'admin')
  ) with check (
    public.is_super_admin()
    or (tenant_id = public.jwt_tenant_id() and public.jwt_role() = 'admin')
  );

-- Generic tenant+org-scoped policies for the org-bearing domain tables
do $$
declare t text;
begin
  foreach t in array array['policies','policy_documents','alerts','approvals','document_chunks'] loop
    -- read: my tenant + accessible orgs (parent roll-up)
    execute format($p$
      create policy %1$s_read on public.%1$s for select using (
        public.is_super_admin()
        or (tenant_id = public.jwt_tenant_id()
            and (org_id is null or org_id in (select public.accessible_org_ids())))
      );$p$, t);
    -- write: same scope, excluding viewers
    execute format($p$
      create policy %1$s_write on public.%1$s for all using (
        public.is_super_admin()
        or (tenant_id = public.jwt_tenant_id()
            and public.jwt_role() in ('admin','manager','owner')
            and (org_id is null or org_id in (select public.accessible_org_ids())))
      ) with check (
        public.is_super_admin()
        or (tenant_id = public.jwt_tenant_id()
            and public.jwt_role() in ('admin','manager','owner')
            and (org_id is null or org_id in (select public.accessible_org_ids())))
      );$p$, t);
  end loop;
end $$;

-- Tenant-scoped (no org column) tables: scope by tenant_id
do $$
declare t text;
begin
  foreach t in array array[
    'providers','alert_rules','notification_log','subscriptions','invoices',
    'billing_events','api_keys','webhooks','audit_log','invitations'
  ] loop
    execute format($p$
      create policy %1$s_tenant_read on public.%1$s for select using (
        public.is_super_admin() or tenant_id = public.jwt_tenant_id()
      );$p$, t);
    execute format($p$
      create policy %1$s_tenant_write on public.%1$s for all using (
        public.is_super_admin()
        or (tenant_id = public.jwt_tenant_id() and public.jwt_role() in ('admin','manager'))
      ) with check (
        public.is_super_admin()
        or (tenant_id = public.jwt_tenant_id() and public.jwt_role() in ('admin','manager'))
      );$p$, t);
  end loop;
end $$;

-- NOTE: billing/subscription WRITES in practice happen via the service role
-- (FastAPI + Razorpay webhooks), which bypasses RLS. The policies above guard
-- any client-side access. Refine per-action grants with security-auditor.
