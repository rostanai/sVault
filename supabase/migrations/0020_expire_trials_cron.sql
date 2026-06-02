-- 0020_expire_trials_cron.sql
-- Enforce the 14-day trial limit. A daily pg_cron job flips any `trialing`
-- subscription whose trial_ends_at has passed (and which never converted to a
-- paid plan) to `expired`. Once expired, entitlements.resolve_entitlements
-- returns the hard-locked entitlement set (every feature off, all limits 0) and
-- the frontend renders a full upgrade wall — only the billing page stays usable.
--
-- NOTE: the lock is also enforced in real time in resolve_entitlements (it checks
-- trial_ends_at directly), so access is correct the instant the trial lapses even
-- before this nightly job runs. The job exists to keep the stored status column
-- accurate for reporting / admin views.
--
-- Idempotent: cron.schedule upserts by jobname.
select cron.schedule(
  'svault-expire-trials',
  '15 1 * * *',  -- daily 01:15 UTC
  $$update subscriptions
      set status = 'expired', updated_at = now()
    where status = 'trialing'
      and trial_ends_at is not null
      and trial_ends_at < now();$$
);
