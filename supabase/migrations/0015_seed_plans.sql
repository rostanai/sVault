-- 0015_seed_plans.sql
-- Seed the subscription plan catalog (Free / Starter / Professional / Enterprise)
-- with feature flags + limits per docs/PLANS.md. Idempotent (insert-if-absent).
-- Prices are INR/month base (GST added at checkout); adjust via the Super Admin
-- console or here. unlimited = -1.

insert into public.plans (tier, name, description, price_inr, billing_period, is_active, entitlements)
select 'free', 'Free', 'For getting started — core vault + email renewal alerts.', 0, 'monthly', true,
'{"features":{"email_alerts":true,"whatsapp_alerts":false,"sms_alerts":false,"telegram_alerts":false,"rag":false,"analytics":false,"sso":false,"mfa":false,"api":false,"audit_log":false,"document_vault":true},"limits":{"policies":10,"users":1,"alerts_month":200,"documents":20}}'::jsonb
where not exists (select 1 from public.plans where tier='free');

insert into public.plans (tier, name, description, price_inr, billing_period, is_active, entitlements)
select 'starter', 'Starter', 'Multi-channel alerts (WhatsApp, Telegram, Email) for small teams.', 999, 'monthly', true,
'{"features":{"email_alerts":true,"whatsapp_alerts":true,"sms_alerts":false,"telegram_alerts":true,"rag":false,"analytics":false,"sso":false,"mfa":false,"api":false,"audit_log":false,"document_vault":true},"limits":{"policies":100,"users":3,"alerts_month":500,"documents":200}}'::jsonb
where not exists (select 1 from public.plans where tier='starter');

insert into public.plans (tier, name, description, price_inr, billing_period, is_active, entitlements)
select 'professional', 'Professional', 'Full multi-channel alerts, AI "Ask sVault", analytics, MFA, API & audit log.', 2999, 'monthly', true,
'{"features":{"email_alerts":true,"whatsapp_alerts":true,"sms_alerts":true,"telegram_alerts":true,"rag":true,"analytics":true,"sso":false,"mfa":true,"api":true,"audit_log":true,"document_vault":true},"limits":{"policies":-1,"users":15,"alerts_month":-1,"documents":-1}}'::jsonb
where not exists (select 1 from public.plans where tier='professional');

insert into public.plans (tier, name, description, price_inr, billing_period, is_active, entitlements)
select 'enterprise', 'Enterprise', 'Everything in Professional plus SSO, unlimited users, and priority support.', 9999, 'monthly', true,
'{"features":{"email_alerts":true,"whatsapp_alerts":true,"sms_alerts":true,"telegram_alerts":true,"rag":true,"analytics":true,"sso":true,"mfa":true,"api":true,"audit_log":true,"document_vault":true},"limits":{"policies":-1,"users":-1,"alerts_month":-1,"documents":-1}}'::jsonb
where not exists (select 1 from public.plans where tier='enterprise');
