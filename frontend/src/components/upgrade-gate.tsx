"use client";

import { usePathname, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Sparkles, CreditCard } from "lucide-react";

/**
 * Hard paywall for tenants whose 14-day trial has lapsed (or whose subscription
 * has expired). When `locked` is true, every app page is replaced with an
 * upgrade prompt EXCEPT the billing page, so the only action available is to
 * upgrade. Server-side entitlements already deny every gated feature; this is
 * the matching UI wall.
 */
export default function UpgradeGate({
  locked,
  children,
}: {
  locked: boolean;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();

  const onBillingPage = pathname?.startsWith("/app/billing") ?? false;

  if (!locked || onBillingPage) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-[70vh] items-center justify-center">
      <div className="w-full max-w-lg rounded-2xl border bg-card p-8 text-center shadow-sm">
        <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
          <Sparkles className="h-7 w-7 text-primary" />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Your free trial has ended
        </h1>
        <p className="mt-3 text-muted-foreground">
          Your 14-day sVault trial is over. Upgrade to a paid plan to restore
          access to your dashboard, policies, documents, renewal alerts, and
          Ask&nbsp;sVault. Your data is safe and waiting for you.
        </p>
        <Button
          size="lg"
          className="mt-6 w-full"
          onClick={() => router.push("/app/billing")}
        >
          <CreditCard className="mr-2 h-4 w-4" />
          Upgrade now
        </Button>
        <p className="mt-4 text-xs text-muted-foreground">
          Need help choosing a plan? Contact support@svault.rstglobal.in
        </p>
      </div>
    </div>
  );
}
