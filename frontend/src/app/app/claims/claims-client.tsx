"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getClaims,
  type ClaimRead,
  type ClaimStatus,
} from "@/lib/api";
import { formatDate, formatINR, cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  FileWarning,
  AlertTriangle,
} from "lucide-react";

// ── Constants ──────────────────────────────────────────────────────────────

const STATUS_FILTERS: { value: ClaimStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "reported", label: "Reported" },
  { value: "under_review", label: "Under Review" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "settled", label: "Settled" },
  { value: "closed", label: "Closed" },
];

// ── Badge variant helper ──────────────────────────────────────────────────

type BadgeVariant =
  | "secondary"
  | "warning"
  | "success"
  | "destructive"
  | "outline";

function claimStatusVariant(status: string): BadgeVariant {
  switch (status) {
    case "reported":
      return "secondary";
    case "under_review":
      return "warning";
    case "approved":
      return "success";
    case "rejected":
      return "destructive";
    case "settled":
      return "success";
    case "closed":
      return "secondary";
    case "draft":
      return "outline";
    default:
      return "secondary";
  }
}

function claimStatusLabel(status: string): string {
  const map: Record<string, string> = {
    draft: "Draft",
    reported: "Reported",
    under_review: "Under Review",
    approved: "Approved",
    rejected: "Rejected",
    settled: "Settled",
    closed: "Closed",
  };
  return map[status] ?? status;
}

// ── Types ─────────────────────────────────────────────────────────────────

interface Props {
  token: string;
}

// ── Main component ──────────────────────────────────────────────────────────

export default function ClaimsClient({ token }: Props) {
  const router = useRouter();
  const [claims, setClaims] = useState<ClaimRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<ClaimStatus | "all">("all");

  const fetchClaims = useCallback(() => {
    if (!token) return;
    setLoading(true);
    getClaims(token, {
      status: statusFilter === "all" ? undefined : statusFilter,
      limit: 50,
    })
      .then((res) => {
        setClaims(Array.isArray(res) ? res : []);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token, statusFilter]);

  useEffect(() => {
    fetchClaims();
  }, [fetchClaims]);

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <FileWarning className="h-6 w-6 text-brand-600" />
            Claims
          </h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">
            Track insurance claims against your policies.
          </p>
        </div>
      </div>

      {/* Status filter chips */}
      <div className="flex flex-wrap items-center gap-2">
        {STATUS_FILTERS.map((f) => (
          <Button
            key={f.value}
            size="sm"
            variant={statusFilter === f.value ? "default" : "outline"}
            onClick={() => setStatusFilter(f.value)}
            className={cn(
              "rounded-full h-7 px-3 text-xs font-medium",
              statusFilter === f.value
                ? "bg-brand-600 text-white border-brand-600 hover:bg-brand-600/90"
                : "text-zinc-600 dark:text-zinc-400"
            )}
          >
            {f.label}
          </Button>
        ))}
      </div>

      {/* Table / states */}
      {loading ? (
        <TableSkeleton />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchClaims} />
      ) : claims.length === 0 ? (
        <EmptyState hasFilter={statusFilter !== "all"} />
      ) : (
        <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Claim</TableHead>
                <TableHead>Policy</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Claim Amount</TableHead>
                <TableHead>Incident Date</TableHead>
                <TableHead>Reported</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {claims.map((claim) => (
                <TableRow
                  key={claim.id}
                  className="cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/60"
                  onClick={() => router.push(`/app/claims/${claim.id}`)}
                  aria-label={`View claim ${claim.claim_number ?? claim.id.slice(0, 8)}`}
                >
                  {/* Claim identifier */}
                  <TableCell>
                    <span className="font-medium font-mono text-sm">
                      {claim.claim_number ?? claim.id.slice(0, 8) + "…"}
                    </span>
                  </TableCell>

                  {/* Policy link */}
                  <TableCell>
                    {claim.policy_title ? (
                      <Link
                        href={`/app/policies/${claim.policy_id}`}
                        className="text-brand-600 hover:underline dark:text-brand-400 font-medium text-sm"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {claim.policy_title}
                      </Link>
                    ) : (
                      <span className="text-xs text-zinc-400 font-mono">
                        {claim.policy_id.slice(0, 8)}…
                      </span>
                    )}
                  </TableCell>

                  {/* Status badge */}
                  <TableCell>
                    <Badge
                      variant={claimStatusVariant(claim.status)}
                      className={cn(
                        claim.status === "settled"
                          ? "bg-indigo-100 text-indigo-700 border-indigo-200 dark:bg-indigo-900/30 dark:text-indigo-300 dark:border-indigo-800"
                          : "",
                        claim.status === "closed"
                          ? "bg-zinc-100 text-zinc-600 border-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:border-zinc-700"
                          : ""
                      )}
                    >
                      {claimStatusLabel(claim.status)}
                    </Badge>
                  </TableCell>

                  {/* Claim amount */}
                  <TableCell className="tabular-nums text-sm">
                    {formatINR(claim.claim_amount_inr)}
                  </TableCell>

                  {/* Incident date */}
                  <TableCell className="text-zinc-500 text-sm whitespace-nowrap">
                    {formatDate(claim.incident_date)}
                  </TableCell>

                  {/* Reported date */}
                  <TableCell className="text-zinc-500 text-sm whitespace-nowrap">
                    {formatDate(claim.reported_date)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Note about creating claims */}
      {!loading && !error && (
        <p className="text-xs text-zinc-400 dark:text-zinc-500">
          To file a new claim, open the relevant policy and use the &ldquo;File a claim&rdquo; action there.
        </p>
      )}
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────

function TableSkeleton() {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <div className="p-4 space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────

function EmptyState({ hasFilter }: { hasFilter: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <FileWarning className="mb-3 h-10 w-10 text-zinc-300" />
      <h3 className="font-semibold">
        {hasFilter ? "No matching claims" : "No claims yet"}
      </h3>
      <p className="mt-1 text-sm text-zinc-400">
        {hasFilter
          ? "Try selecting a different status filter."
          : "File a claim from a policy's page when you need to report an incident."}
      </p>
    </div>
  );
}

// ── Error state ───────────────────────────────────────────────────────────

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <AlertTriangle className="mb-3 h-10 w-10 text-red-400" />
      <h3 className="font-semibold">Failed to load claims</h3>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
      <Button size="sm" variant="outline" className="mt-4" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}
