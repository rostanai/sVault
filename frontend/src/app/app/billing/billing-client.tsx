"use client";

import { useEffect, useState } from "react";
import {
  getPlans,
  getSubscription,
  type PlanRead,
  type SubscriptionWithEntitlements,
} from "@/lib/api";
import { formatDate, formatINR } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Check, AlertTriangle, Zap } from "lucide-react";
import { toast } from "sonner";

interface Props {
  token: string;
}

export default function BillingClient({ token }: Props) {
  const [plans, setPlans] = useState<PlanRead[]>([]);
  const [subData, setSubData] = useState<SubscriptionWithEntitlements | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError("No active session.");
      setLoading(false);
      return;
    }
    Promise.all([getPlans(token), getSubscription(token)])
      .then(([plansRes, subRes]) => {
        setPlans(plansRes);
        setSubData(subRes);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <BillingSkeleton />;
  if (error) return <ErrorState message={error} />;

  const sub = subData?.subscription;
  const currentPlanId = sub?.plan_id;

  const trialEndsAt = sub?.trial_ends_at;
  const trialDaysLeft = trialEndsAt
    ? Math.ceil((new Date(trialEndsAt).getTime() - Date.now()) / 86400000)
    : null;

  const isTrialing = sub?.status === "trialing";

  return (
    <div className="space-y-8 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Billing</h2>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Manage your subscription and plan
        </p>
      </div>

      {/* Current subscription status */}
      {sub && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold">
              Current Subscription
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center gap-4">
              <div>
                <p className="text-xs text-zinc-500 uppercase tracking-wide">Status</p>
                <div className="mt-1">
                  <SubscriptionStatusBadge status={sub.status} />
                </div>
              </div>
              {isTrialing && trialDaysLeft != null && (
                <div>
                  <p className="text-xs text-zinc-500 uppercase tracking-wide">
                    Trial ends
                  </p>
                  <p className="mt-1 text-sm font-medium">
                    {formatDate(trialEndsAt)}{" "}
                    <span
                      className={
                        trialDaysLeft <= 3 ? "text-red-600" : "text-zinc-500"
                      }
                    >
                      ({trialDaysLeft}d left)
                    </span>
                  </p>
                </div>
              )}
              {sub.current_period_end && !isTrialing && (
                <div>
                  <p className="text-xs text-zinc-500 uppercase tracking-wide">
                    Next billing
                  </p>
                  <p className="mt-1 text-sm font-medium">
                    {formatDate(sub.current_period_end)}
                  </p>
                </div>
              )}
              {sub.cancel_at_period_end && (
                <div>
                  <p className="text-xs text-amber-600 font-medium">
                    Cancels at period end
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Trial banner */}
      {isTrialing && trialDaysLeft != null && trialDaysLeft <= 7 && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-800 dark:bg-amber-950">
          <Zap className="h-5 w-5 shrink-0 text-amber-600" />
          <p className="text-sm text-amber-800 dark:text-amber-200">
            Your trial ends in <strong>{trialDaysLeft} days</strong>. Upgrade
            to a paid plan to keep access to all features.
          </p>
        </div>
      )}

      {/* Plans */}
      <div>
        <h3 className="mb-4 text-base font-semibold">Available Plans</h3>
        {plans.length === 0 ? (
          <p className="text-sm text-zinc-400">No plans available.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {plans.map((plan) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                isCurrent={plan.id === currentPlanId}
                onUpgrade={() => {
                  // Razorpay integration — stub with toast for now
                  toast.info(
                    `Razorpay checkout for "${plan.name}" coming soon.`
                  );
                }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function PlanCard({
  plan,
  isCurrent,
  onUpgrade,
}: {
  plan: PlanRead;
  isCurrent: boolean;
  onUpgrade: () => void;
}) {
  const entitlements = Object.entries(plan.entitlements ?? {}).slice(0, 5);

  return (
    <Card
      className={
        isCurrent
          ? "border-brand-500 ring-2 ring-brand-500/30"
          : ""
      }
    >
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="capitalize">{plan.name}</CardTitle>
          {isCurrent && (
            <Badge variant="default" className="text-xs">
              Current
            </Badge>
          )}
        </div>
        {plan.description && (
          <CardDescription>{plan.description}</CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Price */}
        <div>
          {parseFloat(plan.price_inr) === 0 ? (
            <p className="text-3xl font-bold">Free</p>
          ) : (
            <div>
              <span className="text-3xl font-bold">
                {formatINR(plan.price_inr)}
              </span>
              <span className="text-sm text-zinc-500">
                /{plan.billing_period}
              </span>
            </div>
          )}
        </div>

        {/* Entitlements sample */}
        {entitlements.length > 0 && (
          <ul className="space-y-1.5">
            {entitlements.map(([key, val]) => (
              <li key={key} className="flex items-center gap-2 text-sm">
                <Check className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
                <span className="text-zinc-600 dark:text-zinc-400">
                  {String(key).replace(/_/g, " ")}
                  {typeof val === "number" && val > 0 ? `: ${val}` : ""}
                  {typeof val === "boolean" && !val ? " (limited)" : ""}
                </span>
              </li>
            ))}
          </ul>
        )}

        {isCurrent ? (
          <Button variant="outline" className="w-full" disabled>
            Current Plan
          </Button>
        ) : (
          <Button className="w-full" onClick={onUpgrade}>
            Upgrade to {plan.name}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function SubscriptionStatusBadge({ status }: { status: string }) {
  const variants: Record<string, "success" | "warning" | "destructive" | "secondary"> = {
    trialing: "warning",
    active: "success",
    cancelled: "destructive",
    past_due: "destructive",
    expired: "destructive",
  };
  return (
    <Badge variant={variants[status] ?? "secondary"} className="capitalize">
      {status.replace(/_/g, " ")}
    </Badge>
  );
}

function BillingSkeleton() {
  return (
    <div className="space-y-8 max-w-4xl">
      <div className="space-y-1">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-4 w-48" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-40" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-12 w-64" />
        </CardContent>
      </Card>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-5 w-24" />
            </CardHeader>
            <CardContent className="space-y-3">
              <Skeleton className="h-8 w-32" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-9 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <AlertTriangle className="mb-3 h-10 w-10 text-red-400" />
      <h3 className="font-semibold">Failed to load billing info</h3>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
    </div>
  );
}
