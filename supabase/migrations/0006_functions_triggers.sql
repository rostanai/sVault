-- 0006 — Functions & triggers (updated_at, new-user, policy status, audit)

-- Generic updated_at maintainer
create or replace function public.set_updated_at() returns trigger
  language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

do $$
declare t text;
begin
  foreach t in array array[
    'plans','tenants','organizations','profiles','subscriptions',
    'providers','policies','alert_rules'
  ] loop
    execute format(
      'create trigger trg_%1$s_updated before update on public.%1$s
         for each row execute function public.set_updated_at();', t);
  end loop;
end $$;

-- New auth user -> create a profile row (tenant/org/role filled by signup flow / invite)
create or replace function public.handle_new_user() returns trigger
  language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email, full_name)
  values (new.id, new.email, new.raw_user_meta_data ->> 'full_name')
  on conflict (id) do nothing;
  return new;
end $$;

create trigger trg_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Derive policy status from dates (active/expiring/lapsed) unless explicitly draft/cancelled/renewed
create or replace function public.compute_policy_status() returns trigger
  language plpgsql as $$
begin
  if new.status in ('draft','pending_approval','cancelled','renewed') then
    return new;
  end if;
  if new.expiry_date is null then
    new.status := 'active';
  elsif new.expiry_date < current_date then
    new.status := 'lapsed';
  elsif new.expiry_date <= current_date + 60 then
    new.status := 'expiring';
  else
    new.status := 'active';
  end if;
  return new;
end $$;

create trigger trg_policy_status
  before insert or update of expiry_date, status on public.policies
  for each row execute function public.compute_policy_status();

-- Lightweight audit trigger for key tables
create or replace function public.audit_row() returns trigger
  language plpgsql security definer set search_path = public as $$
declare act audit_action;
begin
  act := case tg_op when 'INSERT' then 'create' when 'UPDATE' then 'update' else 'delete' end;
  insert into public.audit_log(tenant_id, actor, action, entity_type, entity_id, detail)
  values (
    coalesce(new.tenant_id, old.tenant_id),
    auth.uid(), act, tg_table_name,
    coalesce(new.id, old.id),
    case when tg_op='DELETE' then to_jsonb(old) else to_jsonb(new) end
  );
  return coalesce(new, old);
end $$;

do $$
declare t text;
begin
  foreach t in array array['policies','policy_documents','approvals','subscriptions','api_keys'] loop
    execute format(
      'create trigger trg_audit_%1$s after insert or update or delete on public.%1$s
         for each row execute function public.audit_row();', t);
  end loop;
end $$;
