"use client";

import { useEffect, useState, useCallback } from "react";
import Script from "next/script";
import {
  getInvoices,
  getPlans,
  getSubscription,
  subscribe,
  type InvoiceRead,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Check, AlertTriangle, Zap, Download, FileText, Loader2 } from "lucide-react";
import { toast } from "sonner";

// Allow TypeScript to recognise the globally injected Razorpay script.
declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    Razorpay: any;
  }
}

interface Props {
  token: string;
}

export default function BillingClient({ token }: Props) {
  const [plans, setPlans] = useState<PlanRead[]>([]);
  const [subData, setSubData] = useState<SubscriptionWithEntitlements | null>(null);
  const [invoices, setInvoices] = useState<InvoiceRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [upgradingPlanId, setUpgradingPlanId] = useState<string | null>(null);

  const refreshSubscription = useCallback(() => {
    getSubscription(token)
      .then(setSubData)
      .catch(() => {/* silent — subscription will just stay stale */});
  }, [token]);

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
    // Invoices are independent; a missing endpoint must not break the page.
    getInvoices(token)
      .then(setInvoices)
      .catch(() => setInvoices([]));
  }, [token]);

  async function handleUpgrade(plan: PlanRead) {
    if (!token) return;
    setUpgradingPlanId(plan.id);
    try {
      const result = await subscribe(token, plan.id);

      if (result.razorpay_subscription_id) {
        // Prefer the Razorpay in-app checkout widget.
        if (typeof window.Razorpay !== "undefined") {
          const rzp = new window.Razorpay({
            key: process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID,
            subscription_id: result.razorpay_subscription_id,
            name: "sVault",
            description: plan.name,
            theme: { color: "#2746c9" },
            handler: () => {
              toast.success("Payment received — your plan is activating.", {
                description: "This may take a moment to reflect.",
                duration: 6000,
              });
              // Refresh subscription status so UI updates.
              setTimeout(refreshSubscription, 3000);
            },
          });
          rzp.open();
        } else if (result.short_url) {
          // Razorpay script didn't load (e.g. ad-blocker) — open the hosted page.
          window.open(result.short_url, "_blank", "noopener,noreferrer");
          toast.info("Complete your payment in the new tab.", {
            description: "The page will update once payment is confirmed.",
          });
        } else {
          toast.success("Subscription created. Awaiting payment confirmation.");
        }
      } else if (result.short_url) {
        // No Razorpay subscription ID yet (plan not configured in Razorpay) — open short URL.
        window.open(result.short_url, "_blank", "noopener,noreferrer");
      } else {
        // Local/dev mode — subscription created without Razorpay keys.
        toast.success(`Switched to ${plan.name} plan.`, {
          description: "No payment required in this environment.",
        });
        refreshSubscription();
      }
    } catch {
      // apiFetch already showed a toast via the error envelope; nothing extra needed.
    } finally {
      setUpgradingPlanId(null);
    }
  }

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
    <>
      {/* Razorpay checkout.js — loaded once, async, so it doesn't block page. */}
      <Script
        src="https://checkout.razorpay.com/v1/checkout.js"
        strategy="lazyOnload"
      />

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
                  isUpgrading={upgradingPlanId === plan.id}
                  onUpgrade={() => handleUpgrade(plan)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Billing history */}
        <div>
          <h3 className="mb-4 text-base font-semibold">Billing History</h3>
          {invoices.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-10 text-center">
                <FileText className="mb-2 h-8 w-8 text-zinc-300" />
                <p className="text-sm text-zinc-500">No invoices yet.</p>
                <p className="text-xs text-zinc-400">
                  Invoices appear here after your first payment.
                </p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>GST</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Invoice</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invoices.map((inv) => (
                    <TableRow key={inv.id}>
                      <TableCell>{formatDate(inv.issued_at)}</TableCell>
                      <TableCell className="font-medium">
                        {formatINR(inv.amount_inr)}
                      </TableCell>
                      <TableCell className="text-zinc-500">
                        {formatINR(inv.gst_inr)}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={inv.status === "paid" ? "success" : "secondary"}
                          className="capitalize"
                        >
                          {inv.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        {inv.pdf_url ? (
                          <Button asChild variant="outline" size="sm">
                            <a
                              href={inv.pdf_url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <Download className="mr-1.5 h-3.5 w-3.5" />
                              Download
                            </a>
                          </Button>
                        ) : (
                          <span className="text-xs text-zinc-400">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}

// Sub-components

function PlanCard({
  plan,
  isCurrent,
  isUpgrading,
  onUpgrade,
}: {
  plan: PlanRead;
  isCurrent: boolean;
  isUpgrading: boolean;
  onUpgrade: () => void;
}) {
  const ent = (plan.entitlements ?? {}) as {
    features?: Record<string, boolean>;
    limits?: Record<string, number>;
  };
  const features = ent.features ?? {};
  const limits = ent.limits ?? {};
  const FEATURE_LABELS: [string, string][] = [
    ["email_alerts", "Email alerts"],
    ["whatsapp_alerts", "WhatsApp alerts"],
    ["sms_alerts", "SMS alerts"],
    ["telegram_alerts", "Telegram alerts"],
    ["rag", "AI “Ask sVault”"],
    ["analytics", "Analytics"],
    ["mfa", "Multi-factor auth"],
    ["sso", "Single sign-on (SSO)"],
    ["api", "Developer API"],
    ["audit_log", "Audit log"],
    ["document_vault", "Document vault"],
  ];
  const fmtLimit = (v: number | undefined) =>
    v === -1 ? "Unlimited" : v == null ? "—" : String(v);

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

        {/* Limits */}
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-zinc-500 dark:text-zinc-400">
          <span>
            Policies:{" "}
            <span className="font-medium text-zinc-700 dark:text-zinc-300">
              {fmtLimit(limits.policies)}
            </span>
          </span>
          <span>
            Users:{" "}
            <span className="font-medium text-zinc-700 dark:text-zinc-300">
              {fmtLimit(limits.users)}
            </span>
          </span>
          <span>
            Alerts/mo:{" "}
            <span className="font-medium text-zinc-700 dark:text-zinc-300">
              {fmtLimit(limits.alerts_month)}
            </span>
          </span>
          <span>
            Documents:{" "}
            <span className="font-medium text-zinc-700 dark:text-zinc-300">
              {fmtLimit(limits.documents)}
            </span>
          </span>
        </div>

        {/* Full feature checklist */}
        <ul className="space-y-1.5 border-t border-zinc-100 pt-3 dark:border-zinc-800">
          {FEATURE_LABELS.map(([key, label]) => {
            const on = !!features[key];
            return (
              <li key={key} className="flex items-center gap-2 text-sm">
                {on ? (
                  <Check className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
                ) : (
                  <span
                    aria-hidden="true"
                    className="h-3.5 w-3.5 shrink-0 text-center leading-none text-zinc-300 dark:text-zinc-600"
                  >
                    –
                  </span>
                )}
                <span
                  className={
                    on
                      ? "text-zinc-700 dark:text-zinc-300"
                      : "text-zinc-400 line-through dark:text-zinc-600"
                  }
                >
                  {label}
                </span>
              </li>
            );
          })}
        </ul>

        {isCurrent ? (
          <Button variant="outline" className="w-full" disabled>
            Current Plan
          </Button>
        ) : (
          <Button
            className="w-full"
            onClick={onUpgrade}
            disabled={isUpgrading}
          >
            {isUpgrading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Opening checkout…
              </>
            ) : (
              `Upgrade to ${plan.name}`
            )}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function SubscriptionStatusBadge({ status }: { status: string }) {
  const variants: Record<
    string,
    "success" | "warning" | "destructive" | "secondary"
  > = {
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
