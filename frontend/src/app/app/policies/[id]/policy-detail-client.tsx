"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getPolicy, type PolicyRead } from "@/lib/api";
import {
  formatDate,
  formatINR,
  daysLeftVariant,
  categorylabel,
  statusLabel,
} from "@/lib/utils";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { ArrowLeft, AlertTriangle } from "lucide-react";

interface Props {
  id: string;
  token: string;
}

export default function PolicyDetailClient({ id, token }: Props) {
  const [policy, setPolicy] = useState<PolicyRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError("No active session.");
      setLoading(false);
      return;
    }
    getPolicy(token, id)
      .then(setPolicy)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id, token]);

  if (loading) return <DetailSkeleton />;
  if (error) return <ErrorState message={error} />;
  if (!policy) return null;

  const daysLeft = policy.expiry_date
    ? Math.ceil(
        (new Date(policy.expiry_date).getTime() - Date.now()) / 86400000
      )
    : null;

  const fields: { label: string; value: string }[] = [
    { label: "Policy Number", value: policy.policy_number ?? "—" },
    { label: "Category", value: categorylabel(policy.category) },
    { label: "Status", value: statusLabel(policy.status) },
    { label: "Sum Insured", value: formatINR(policy.sum_insured_inr) },
    { label: "Annual Premium", value: formatINR(policy.premium_inr) },
    { label: "GST", value: formatINR(policy.gst_inr) },
    { label: "Inception Date", value: formatDate(policy.inception_date) },
    { label: "Expiry Date", value: formatDate(policy.expiry_date) },
    { label: "Renewal Date", value: formatDate(policy.renewal_date) },
    { label: "Created", value: formatDate(policy.created_at) },
  ];

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Back */}
      <div>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/app/policies" className="flex items-center gap-1.5">
            <ArrowLeft className="h-4 w-4" />
            Back to Policies
          </Link>
        </Button>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">{policy.title}</h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            {categorylabel(policy.category)}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <Badge
            variant={
              policy.status === "active"
                ? "success"
                : policy.status === "expiring"
                ? "warning"
                : policy.status === "lapsed" || policy.status === "cancelled"
                ? "destructive"
                : "secondary"
            }
          >
            {statusLabel(policy.status)}
          </Badge>
          {daysLeft != null && (
            <Badge variant={daysLeftVariant(daysLeft)} className="text-xs">
              {daysLeft < 0
                ? `Expired ${Math.abs(daysLeft)}d ago`
                : `${daysLeft}d left`}
            </Badge>
          )}
        </div>
      </div>

      {/* Details card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Policy Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
            {fields.map(({ label, value }) => (
              <div key={label}>
                <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  {label}
                </dt>
                <dd className="mt-1 text-sm font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      {/* Documents + Alerts stubs */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Documents</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-zinc-400">
            Document upload coming in the next milestone.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Alert Schedule</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-zinc-400">
            Alert configuration coming soon.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-6 max-w-2xl">
      <Skeleton className="h-8 w-20" />
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-32" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-32" />
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="space-y-1">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-4 w-32" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <AlertTriangle className="mb-3 h-10 w-10 text-red-400" />
      <h3 className="font-semibold">Failed to load policy</h3>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
    </div>
  );
}
