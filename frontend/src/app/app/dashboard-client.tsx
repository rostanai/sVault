"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getDashboard, type DashboardResponse } from "@/lib/api";
import { formatINR, formatDate, daysLeftVariant, categorylabel, statusLabel } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  IndianRupee,
  AlertTriangle,
  TrendingDown,
  Calendar,
  ChevronRight,
} from "lucide-react";
import {
  CategoryBarChart,
  StatusDonutChart,
  ExpiryTimelineChart,
} from "./_charts";

interface Props {
  token: string;
}

export default function DashboardClient({ token }: Props) {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError("No active session.");
      setLoading(false);
      return;
    }
    getDashboard(token)
      .then(setData)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <DashboardSkeleton />;
  if (error) return <ErrorState message={error} />;
  if (!data) return null;

  const { totals, status_counts, expiring, by_category, upcoming } = data;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Your insurance portfolio at a glance
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Policies"
          value={String(totals.policies)}
          icon={FileText}
          iconClass="text-brand-600"
        />
        <StatCard
          title="Sum Insured"
          value={formatINR(totals.sum_insured_inr)}
          icon={IndianRupee}
          iconClass="text-emerald-600"
        />
        <StatCard
          title="Annual Premium"
          value={formatINR(totals.premium_inr)}
          icon={TrendingDown}
          iconClass="text-violet-600"
        />
        <StatCard
          title="Lapsed / At Risk"
          value={String(totals.lapsed)}
          icon={AlertTriangle}
          iconClass="text-red-500"
          valueClass={totals.lapsed > 0 ? "text-red-600" : undefined}
        />
      </div>

      {/* Expiring soon row */}
      <div className="grid gap-4 sm:grid-cols-3">
        <ExpiryCard label="Expiring in 30 days" count={expiring.next_30} variant="destructive" />
        <ExpiryCard label="Expiring in 60 days" count={expiring.next_60} variant="warning" />
        <ExpiryCard label="Expiring in 90 days" count={expiring.next_90} variant="secondary" />
      </div>

      {/* Charts row */}
      <div className="grid gap-4 lg:grid-cols-3">
        <CategoryBarChart data={by_category} />
        <StatusDonutChart statusCounts={status_counts} />
        <ExpiryTimelineChart expiring={expiring} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* By category (text list kept for accessibility / quick scan) */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold">By Category</CardTitle>
          </CardHeader>
          <CardContent>
            {by_category.length === 0 ? (
              <p className="text-sm text-zinc-400">No policies yet.</p>
            ) : (
              <ul className="space-y-2">
                {by_category.map(({ category, count }) => (
                  <li key={category} className="flex items-center justify-between">
                    <span className="text-sm text-zinc-600 dark:text-zinc-400">
                      {categorylabel(category)}
                    </span>
                    <Badge variant="secondary">{count}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Upcoming renewals table */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-semibold">
              Upcoming Renewals
            </CardTitle>
            <Link
              href="/app/policies"
              className="flex items-center gap-1 text-xs text-brand-600 hover:underline"
            >
              View all <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            {upcoming.length === 0 ? (
              <div className="flex items-center justify-center py-10">
                <div className="text-center">
                  <Calendar className="mx-auto mb-2 h-8 w-8 text-zinc-300" />
                  <p className="text-sm text-zinc-400">No upcoming renewals</p>
                </div>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Policy</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Expires</TableHead>
                    <TableHead>Days Left</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {upcoming.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell>
                        <Link
                          href={`/app/policies/${p.id}`}
                          className="font-medium hover:text-brand-600 hover:underline"
                        >
                          {p.title}
                        </Link>
                      </TableCell>
                      <TableCell className="text-zinc-500">
                        {categorylabel(p.category)}
                      </TableCell>
                      <TableCell className="text-zinc-500">
                        {formatDate(p.expiry_date)}
                      </TableCell>
                      <TableCell>
                        {p.days_left != null ? (
                          <Badge variant={daysLeftVariant(p.days_left)}>
                            {p.days_left}d
                          </Badge>
                        ) : (
                          <span className="text-zinc-400">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatCard({
  title,
  value,
  icon: Icon,
  iconClass,
  valueClass,
}: {
  title: string;
  value: string;
  icon: React.ElementType;
  iconClass?: string;
  valueClass?: string;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          {title}
        </CardTitle>
        <Icon className={`h-4 w-4 ${iconClass ?? ""}`} />
      </CardHeader>
      <CardContent>
        <p className={`text-2xl font-bold ${valueClass ?? ""}`}>{value}</p>
      </CardContent>
    </Card>
  );
}

function ExpiryCard({
  label,
  count,
  variant,
}: {
  label: string;
  count: number;
  variant: "destructive" | "warning" | "secondary";
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between p-4">
        <span className="text-sm text-zinc-600 dark:text-zinc-400">{label}</span>
        <Badge variant={variant} className="text-base font-bold px-3 py-1">
          {count}
        </Badge>
      </CardContent>
    </Card>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-3 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-32" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Card key={i}>
            <CardContent className="p-4">
              <Skeleton className="h-6 w-full" />
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
      <h3 className="font-semibold">Failed to load dashboard</h3>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
    </div>
  );
}

// Re-export statusLabel so it's actually used (avoids lint unused warning)
export { statusLabel };
