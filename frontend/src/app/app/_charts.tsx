"use client";

/**
 * Pure SVG/CSS chart components for the sVault dashboard.
 * No external chart library — zero new dependencies.
 */

import { categorylabel, statusLabel } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// ── Types ───────────────────────────────────────────────────────────────────────

interface CategoryEntry {
  category: string;
  count: number;
}

interface StatusCounts {
  [key: string]: number;
}

interface ExpiringCounts {
  next_30: number;
  next_60: number;
  next_90: number;
}

// ── Color helpers ──────────────────────────────────────────────────────────────

/** Returns Tailwind bg class for a policy status key */
function statusColorClass(status: string): string {
  switch (status) {
    case "active":
      return "bg-emerald-500";
    case "expiring":
      return "bg-amber-400";
    case "lapsed":
      return "bg-red-500";
    case "cancelled":
      return "bg-red-400";
    case "renewed":
      return "bg-brand-600";
    case "draft":
      return "bg-zinc-400";
    case "pending_approval":
      return "bg-violet-400";
    default:
      return "bg-zinc-400";
  }
}

/** Returns hex color string for SVG use (status donut) */
function statusHexColor(status: string): string {
  switch (status) {
    case "active":
      return "#10b981"; // emerald-500
    case "expiring":
      return "#fbbf24"; // amber-400
    case "lapsed":
      return "#ef4444"; // red-500
    case "cancelled":
      return "#f87171"; // red-400
    case "renewed":
      return "#6366f1"; // indigo-500 (brand-600 approximation)
    case "draft":
      return "#a1a1aa"; // zinc-400
    case "pending_approval":
      return "#a78bfa"; // violet-400
    default:
      return "#a1a1aa";
  }
}

// ── 1. Policies by Category — Horizontal Bar Chart ────────────────────────────

export function CategoryBarChart({ data }: { data: CategoryEntry[] }) {
  const hasData = data.length > 0 && data.some((d) => d.count > 0);
  const maxCount = hasData ? Math.max(...data.map((d) => d.count)) : 0;

  const ariaLabel = hasData
    ? `Policies by category: ${data.map((d) => `${categorylabel(d.category)} ${d.count}`).join(", ")}`
    : "No policy data available";

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold">Policies by Category</CardTitle>
      </CardHeader>
      <CardContent>
        <div
          role="img"
          aria-label={ariaLabel}
          className="space-y-3"
        >
          {!hasData ? (
            <p className="text-sm text-zinc-400 py-4 text-center">No data yet</p>
          ) : (
            data.map(({ category, count }) => {
              const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
              return (
                <div key={category} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-zinc-600 dark:text-zinc-400 truncate pr-2 max-w-[160px]">
                      {categorylabel(category)}
                    </span>
                    <span className="font-semibold text-zinc-800 dark:text-zinc-200 tabular-nums">
                      {count}
                    </span>
                  </div>
                  <div
                    className="h-2 w-full rounded-full bg-zinc-100 dark:bg-zinc-800 overflow-hidden"
                    aria-hidden="true"
                  >
                    <div
                      className="h-full rounded-full bg-brand-600 transition-all duration-500"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ── 2. Status Breakdown — SVG Donut Chart ─────────────────────────────────────

const DONUT_R = 56;
const DONUT_CX = 70;
const DONUT_CY = 70;
const DONUT_CIRCUMFERENCE = 2 * Math.PI * DONUT_R;

interface DonutSegment {
  status: string;
  count: number;
  color: string;
  offset: number;
  dash: number;
}

function buildDonutSegments(statusCounts: StatusCounts): DonutSegment[] {
  const entries = Object.entries(statusCounts).filter(([, v]) => v > 0);
  const total = entries.reduce((s, [, v]) => s + v, 0);
  if (total === 0) return [];

  let cumulativeOffset = 0;
  // Start from the top (rotate -90deg via offset adjustment)
  const startOffset = DONUT_CIRCUMFERENCE * 0.25;

  return entries.map(([status, count]) => {
    const dash = (count / total) * DONUT_CIRCUMFERENCE;
    const gap = DONUT_CIRCUMFERENCE - dash;
    const offset = DONUT_CIRCUMFERENCE - cumulativeOffset - startOffset;
    cumulativeOffset += dash;
    return {
      status,
      count,
      color: statusHexColor(status),
      offset,
      dash,
    };
  });
}

export function StatusDonutChart({ statusCounts }: { statusCounts: StatusCounts }) {
  const entries = Object.entries(statusCounts).filter(([, v]) => v > 0);
  const total = entries.reduce((s, [, v]) => s + v, 0);
  const hasData = total > 0;

  const segments = buildDonutSegments(statusCounts);

  const ariaLabel = hasData
    ? `Status breakdown — total ${total} policies: ${entries.map(([s, v]) => `${statusLabel(s)} ${v}`).join(", ")}`
    : "No status data available";

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold">Status Breakdown</CardTitle>
      </CardHeader>
      <CardContent>
        <div role="img" aria-label={ariaLabel}>
          {!hasData ? (
            <p className="text-sm text-zinc-400 py-4 text-center">No data yet</p>
          ) : (
            <div className="flex items-center gap-6 flex-wrap">
              {/* SVG donut */}
              <svg
                width="140"
                height="140"
                viewBox="0 0 140 140"
                aria-hidden="true"
                className="shrink-0"
              >
                {/* Background ring */}
                <circle
                  cx={DONUT_CX}
                  cy={DONUT_CY}
                  r={DONUT_R}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="20"
                  className="text-zinc-100 dark:text-zinc-800"
                />
                {segments.map((seg) => (
                  <circle
                    key={seg.status}
                    cx={DONUT_CX}
                    cy={DONUT_CY}
                    r={DONUT_R}
                    fill="none"
                    stroke={seg.color}
                    strokeWidth="20"
                    strokeDasharray={`${seg.dash} ${DONUT_CIRCUMFERENCE - seg.dash}`}
                    strokeDashoffset={seg.offset}
                    strokeLinecap="butt"
                  />
                ))}
                {/* Center label */}
                <text
                  x={DONUT_CX}
                  y={DONUT_CY - 6}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="fill-zinc-800 dark:fill-zinc-100"
                  style={{ fontSize: 22, fontWeight: 700, fill: "currentColor" }}
                >
                  {total}
                </text>
                <text
                  x={DONUT_CX}
                  y={DONUT_CY + 14}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  style={{ fontSize: 10, fill: "#71717a" }}
                >
                  total
                </text>
              </svg>

              {/* Legend */}
              <ul className="space-y-2 text-xs min-w-[120px]">
                {entries.map(([status, count]) => (
                  <li key={status} className="flex items-center gap-2">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: statusHexColor(status) }}
                      aria-hidden="true"
                    />
                    <span className="text-zinc-600 dark:text-zinc-400 capitalize truncate">
                      {statusLabel(status)}
                    </span>
                    <span className="ml-auto font-semibold text-zinc-800 dark:text-zinc-200 tabular-nums">
                      {count}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ── 3. Expiry Timeline — Segmented Bar Chart ──────────────────────────────────

interface ExpiryBarProps {
  expiring: ExpiringCounts;
}

interface ExpiryBucket {
  label: string;
  sublabel: string;
  count: number;
  barClass: string;
  textClass: string;
}

export function ExpiryTimelineChart({ expiring }: ExpiryBarProps) {
  const buckets: ExpiryBucket[] = [
    {
      label: "≤ 30 days",
      sublabel: "Critical",
      count: expiring.next_30,
      barClass: "bg-red-500",
      textClass: "text-red-600 dark:text-red-400",
    },
    {
      label: "31–60 days",
      sublabel: "Warning",
      count: Math.max(0, expiring.next_60 - expiring.next_30),
      barClass: "bg-amber-400",
      textClass: "text-amber-600 dark:text-amber-400",
    },
    {
      label: "61–90 days",
      sublabel: "Notice",
      count: Math.max(0, expiring.next_90 - expiring.next_60),
      barClass: "bg-yellow-300",
      textClass: "text-yellow-600 dark:text-yellow-400",
    },
  ];

  const maxCount = Math.max(...buckets.map((b) => b.count), 1);
  const hasData = buckets.some((b) => b.count > 0);

  const ariaLabel = `Expiry timeline: ${buckets.map((b) => `${b.label} — ${b.count} ${b.count === 1 ? "policy" : "policies"}`).join("; ")}`;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold">Expiry Timeline</CardTitle>
      </CardHeader>
      <CardContent>
        <div role="img" aria-label={ariaLabel}>
          {!hasData ? (
            <p className="text-sm text-zinc-400 py-4 text-center">No upcoming expirations</p>
          ) : (
            <div className="space-y-4">
              {buckets.map((bucket) => {
                const pct = (bucket.count / maxCount) * 100;
                return (
                  <div key={bucket.label} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <div>
                        <span className="font-medium text-zinc-700 dark:text-zinc-300">
                          {bucket.label}
                        </span>
                        <span className="ml-1.5 text-zinc-400">{bucket.sublabel}</span>
                      </div>
                      <span className={`font-bold tabular-nums ${bucket.textClass}`}>
                        {bucket.count}
                      </span>
                    </div>
                    <div
                      className="h-3 w-full rounded-full bg-zinc-100 dark:bg-zinc-800 overflow-hidden"
                      aria-hidden="true"
                    >
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${bucket.barClass}`}
                        style={{ width: bucket.count === 0 ? "0%" : `${Math.max(pct, 4)}%` }}
                      />
                    </div>
                  </div>
                );
              })}

              {/* Stacked summary bar */}
              <div className="pt-2" aria-hidden="true">
                <p className="text-xs text-zinc-400 mb-1.5">Total in 90 days</p>
                <div className="h-4 w-full rounded-full overflow-hidden flex bg-zinc-100 dark:bg-zinc-800">
                  {buckets.map((bucket) => {
                    const pct = expiring.next_90 > 0
                      ? (bucket.count / expiring.next_90) * 100
                      : 0;
                    return bucket.count > 0 ? (
                      <div
                        key={bucket.label}
                        className={`h-full ${bucket.barClass}`}
                        style={{ width: `${pct}%` }}
                        title={`${bucket.label}: ${bucket.count}`}
                      />
                    ) : null;
                  })}
                </div>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 text-right">
                  {expiring.next_90} {expiring.next_90 === 1 ? "policy" : "policies"} expiring
                </p>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
