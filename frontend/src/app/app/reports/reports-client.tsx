"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getRenewalReport,
  exportRenewalReport,
  type RenewalReportRow,
} from "@/lib/api";
import {
  formatDate,
  formatINR,
  categorylabel,
  statusLabel,
  daysLeftVariant,
  cn,
} from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
  FileText,
  Download,
  AlertTriangle,
  RefreshCw,
  Loader2,
} from "lucide-react";

// ── Window selector options ──────────────────────────────────────────────────────────

const WINDOW_OPTIONS: { value: number; label: string }[] = [
  { value: 30, label: "30 days" },
  { value: 60, label: "60 days" },
  { value: 90, label: "90 days" },
  { value: 180, label: "180 days" },
];

// ── Props ────────────────────────────────────────────────────────────────────────────

interface Props {
  token: string;
}

// ── Main component ───────────────────────────────────────────────────────────────────

export default function ReportsClient({ token }: Props) {
  const [rows, setRows] = useState<RenewalReportRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [windowDays, setWindowDays] = useState(90);

  // Export loading states
  const [exportingCsv, setExportingCsv] = useState(false);
  const [exportingXlsx, setExportingXlsx] = useState(false);

  const fetchReport = useCallback(() => {
    if (!token) return;
    setLoading(true);
    setError(null);
    getRenewalReport(token, { window_days: windowDays })
      .then((data) => {
        setRows(Array.isArray(data) ? data : []);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token, windowDays]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  async function handleExport(format: "csv" | "xlsx") {
    const setSaving = format === "csv" ? setExportingCsv : setExportingXlsx;
    setSaving(true);
    try {
      await exportRenewalReport(token, format, windowDays);
    } catch {
      // downloadAuthed already shows a toast on failure
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-600/10 dark:bg-brand-600/20 shrink-0">
            <FileText
              className="h-5 w-5 text-brand-600 dark:text-brand-400"
              aria-hidden="true"
            />
          </div>
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Reports</h2>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Renewal pipeline and portfolio exports.
            </p>
          </div>
        </div>

        {/* Export controls */}
        <div className="flex items-center gap-2 shrink-0">
          <Button
            size="sm"
            variant="outline"
            onClick={() => handleExport("csv")}
            disabled={exportingCsv || loading}
            aria-label="Export renewal report as CSV"
          >
            {exportingCsv ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Download className="mr-1.5 h-4 w-4" aria-hidden="true" />
            )}
            Export CSV
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => handleExport("xlsx")}
            disabled={exportingXlsx || loading}
            aria-label="Export renewal report as Excel"
          >
            {exportingXlsx ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Download className="mr-1.5 h-4 w-4" aria-hidden="true" />
            )}
            Export Excel
          </Button>
        </div>
      </div>

      {/* Window selector chips */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm text-zinc-500 dark:text-zinc-400 mr-1">
          Show policies expiring within:
        </span>
        {WINDOW_OPTIONS.map((opt) => (
          <Button
            key={opt.value}
            size="sm"
            variant={windowDays === opt.value ? "default" : "outline"}
            onClick={() => setWindowDays(opt.value)}
            className={cn(
              "rounded-full h-7 px-3 text-xs font-medium",
              windowDays === opt.value
                ? "bg-brand-600 text-white border-brand-600 hover:bg-brand-600/90"
                : "text-zinc-600 dark:text-zinc-400"
            )}
            aria-pressed={windowDays === opt.value}
          >
            {opt.label}
          </Button>
        ))}
      </div>

      {/* Table / States */}
      {loading ? (
        <TableSkeleton />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchReport} />
      ) : rows.length === 0 ? (
        <EmptyState windowDays={windowDays} />
      ) : (
        <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Policy</TableHead>
                <TableHead>Provider</TableHead>
                <TableHead>Expiry</TableHead>
                <TableHead>Days Left</TableHead>
                <TableHead className="text-right">Premium</TableHead>
                <TableHead className="text-right">Sum Insured</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => {
                const daysLeft = row.days_left;
                const isExpired = daysLeft != null && daysLeft < 0;

                return (
                  <TableRow key={row.policy_id}>
                    {/* Policy: title + category */}
                    <TableCell>
                      <div className="font-medium">{row.title}</div>
                      <div className="text-xs text-zinc-400 mt-0.5">
                        {categorylabel(row.category)}
                      </div>
                    </TableCell>

                    {/* Provider */}
                    <TableCell className="text-zinc-500">
                      {row.provider_name ?? "—"}
                    </TableCell>

                    {/* Expiry date */}
                    <TableCell className="whitespace-nowrap text-zinc-500">
                      {formatDate(row.expiry_date)}
                    </TableCell>

                    {/* Days left badge */}
                    <TableCell>
                      {daysLeft == null ? (
                        <span className="text-zinc-400">—</span>
                      ) : isExpired ? (
                        <Badge variant="destructive">
                          Expired {Math.abs(daysLeft)}d ago
                        </Badge>
                      ) : (
                        <Badge variant={daysLeftVariant(daysLeft)}>
                          {daysLeft}d left
                        </Badge>
                      )}
                    </TableCell>

                    {/* Premium */}
                    <TableCell className="text-right tabular-nums">
                      {formatINR(row.premium_inr)}
                    </TableCell>

                    {/* Sum insured */}
                    <TableCell className="text-right tabular-nums">
                      {formatINR(row.sum_insured_inr)}
                    </TableCell>

                    {/* Status */}
                    <TableCell>
                      <Badge variant={statusVariant(row.status)}>
                        {statusLabel(row.status)}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>

          {/* Row count footer */}
          <div className="border-t border-zinc-100 px-4 py-2.5 dark:border-zinc-800">
            <p className="text-xs text-zinc-400">
              {rows.length} {rows.length === 1 ? "policy" : "policies"} in window
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Status badge variant ─────────────────────────────────────────────────────────

function statusVariant(
  s: string
): "success" | "warning" | "destructive" | "secondary" {
  if (s === "active") return "success";
  if (s === "expiring") return "warning";
  if (s === "lapsed" || s === "cancelled") return "destructive";
  return "secondary";
}

// ── Skeleton ───────────────────────────────────────────────────────────────────────────────

function TableSkeleton() {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <div className="p-4 space-y-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}

// ── Empty state ──────────────────────────────────────────────────────────────────────

function EmptyState({ windowDays }: { windowDays: number }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <FileText className="mb-3 h-10 w-10 text-zinc-300" aria-hidden="true" />
      <h3 className="font-semibold">No policies expiring in this window</h3>
      <p className="mt-1 text-sm text-zinc-400">
        No active policies expire within the next {windowDays} days.
      </p>
    </div>
  );
}

// ── Error state ──────────────────────────────────────────────────────────────────────

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <AlertTriangle
        className="mb-3 h-10 w-10 text-red-400"
        aria-hidden="true"
      />
      <h3 className="font-semibold">Failed to load report</h3>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
      <Button size="sm" variant="outline" className="mt-4" onClick={onRetry}>
        <RefreshCw className="mr-1.5 h-4 w-4" aria-hidden="true" />
        Retry
      </Button>
    </div>
  );
}
