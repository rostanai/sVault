-- 0009 — Realtime publications (live dashboard / approval / alert updates)

-- Supabase ships a `supabase_realtime` publication. Add the tables whose changes
-- the UI should receive live. (Realtime still enforces RLS per subscriber.)
do $$
begin
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    create publication supabase_realtime;
  end if;
end $$;

alter publication supabase_realtime add table public.policies;
alter publication supabase_realtime add table public.alerts;
alter publication supabase_realtime add table public.approvals;
alter publication supabase_realtime add table public.notification_log;

-- Ensure full row images for updates/deletes over realtime
alter table public.policies     replica identity full;
alter table public.alerts       replica identity full;
alter table public.approvals    replica identity full;
