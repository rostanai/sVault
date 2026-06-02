import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import AppShell from "@/components/app-shell";
import UpgradeGate from "@/components/upgrade-gate";
import { getSubscription, getPlans, getMe } from "@/lib/api";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  const email = user.email ?? "";
  const name =
    (user.user_metadata?.full_name as string | undefined) ??
    email.split("@")[0] ??
    "User";
  const avatarUrl = user.user_metadata?.avatar_url as string | undefined;

  // Best-effort: fetch subscription + plans + super-admin flag server-side.
  // Any error must never block the app shell from rendering.
  let planName: string = "Free";
  let subscriptionStatus: string = "free";
  let trialDaysLeft: number | null = null;
  let isSuperAdmin: boolean = false;
  let locked: boolean = false;
  let token: string = "";

  try {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (session?.access_token) {
      token = session.access_token;
      const [subData, plans, meData] = await Promise.all([
        getSubscription(token),
        getPlans(token),
        getMe(token).catch(() => null),
      ]);

      if (meData?.is_super_admin) {
        isSuperAdmin = true;
      }

      // Server-resolved lock flags (added to /billing/subscription server-side).
      const subExtra = subData as {
        locked?: boolean;
        effective_status?: string;
      } | null;

      // Server-resolved lock: lapsed 14-day trial or expired sub.
      locked = subExtra?.locked === true && !isSuperAdmin;

      const sub = subData?.subscription;
      if (sub) {
        subscriptionStatus = subExtra?.effective_status || sub.status;

        // Resolve plan name from the plans list.
        const matchedPlan = plans.find((p) => p.id === sub.plan_id);
        if (matchedPlan) {
          planName = matchedPlan.name;
        } else if (sub.status === "trialing") {
          planName = "Trial";
        }

        // Compute trial days left.
        if (sub.status === "trialing" && sub.trial_ends_at) {
          const msLeft =
            new Date(sub.trial_ends_at).getTime() - Date.now();
          trialDaysLeft = Math.max(0, Math.ceil(msLeft / 86400000));
        }
      }
    }
  } catch {
    // Billing fetch failed — fall back to "Free" defaults.
  }

  return (
    <AppShell
      email={email}
      name={name}
      avatarUrl={avatarUrl}
      planName={planName}
      subscriptionStatus={subscriptionStatus}
      trialDaysLeft={trialDaysLeft}
      isSuperAdmin={isSuperAdmin}
      token={token}
    >
      <UpgradeGate locked={locked}>{children}</UpgradeGate>
    </AppShell>
  );
}
