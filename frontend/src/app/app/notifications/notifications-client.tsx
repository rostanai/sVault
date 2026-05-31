"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  BellRing,
  Bell,
  CheckSquare,
  Sparkles,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getNotificationHistory, type NotificationItem } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";

// ── Constants ─────────────────────────────────────────────────────────────────

const PAGE_SIZE = 30;

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Mirror the icon logic from app-shell.tsx bell dropdown */
function notifIcon(type: string): React.ElementType {
  if (type === "alert") return Bell;
  if (type === "approval") return CheckSquare;
  return Sparkles;
}

/** Format an ISO date string as a short day label for group headers, e.g. "Today", "Yesterday", "28 May 2026" */
function dayLabel(isoDate: string): string {
  const d = new Date(isoDate);
  if (isNaN(d.getTime())) return "—";

  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  const toDateStr = (dt: Date) =>
    `${dt.getFullYear()}-${dt.getMonth()}-${dt.getDate()}`;

  if (toDateStr(d) === toDateStr(today)) return "Today";
  if (toDateStr(d) === toDateStr(yesterday)) return "Yesterday";
  return d.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/** Group a flat list of notifications by calendar day */
function groupByDay(
  items: NotificationItem[]
): { label: string; items: NotificationItem[] }[] {
  const groups: { label: string; items: NotificationItem[] }[] = [];
  let currentLabel = "";
  let currentGroup: NotificationItem[] = [];

  for (const item of items) {
    const label = dayLabel(item.created_at);
    if (label !== currentLabel) {
      if (currentGroup.length > 0) {
        groups.push({ label: currentLabel, items: currentGroup });
      }
      currentLabel = label;
      currentGroup = [item];
    } else {
      currentGroup.push(item);
    }
  }
  if (currentGroup.length > 0) {
    groups.push({ label: currentLabel, items: currentGroup });
  }
  return groups;
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface Props {
  token: string;
}

// ── Main component ────────────────────────────────────────────────────────────

export default function NotificationsClient({ token }: Props) {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  const fetchPage = useCallback(
    async (pageOffset: number, append: boolean) => {
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const page = await getNotificationHistory(token, {
          limit: PAGE_SIZE,
          offset: pageOffset,
        });
        const results = Array.isArray(page) ? page : [];
        if (append) {
          setItems((prev) => [...prev, ...results]);
        } else {
          setItems(results);
        }
        setHasMore(results.length >= PAGE_SIZE);
        setError(null);
      } catch (err: unknown) {
        const msg =
          err instanceof Error ? err.message : "Failed to load notifications";
        setError(msg);
      }
    },
    [token]
  );

  // Initial load
  useEffect(() => {
    setLoading(true);
    fetchPage(0, false).finally(() => setLoading(false));
  }, [fetchPage]);

  async function handleLoadMore() {
    const nextOffset = offset + PAGE_SIZE;
    setLoadingMore(true);
    await fetchPage(nextOffset, true);
    setOffset(nextOffset);
    setLoadingMore(false);
  }

  async function handleRetry() {
    setLoading(true);
    setOffset(0);
    setHasMore(true);
    await fetchPage(0, false);
    setLoading(false);
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Page header */}
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
          <BellRing
            className="h-6 w-6 text-brand-600 dark:text-brand-400"
            aria-hidden="true"
          />
          Notifications
        </h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Your renewal alerts and approval activity.
        </p>
      </div>

      {/* Content states */}
      {loading ? (
        <NotificationSkeleton />
      ) : error ? (
        <ErrorState message={error} onRetry={handleRetry} />
      ) : items.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <NotificationList items={items} />

          {/* Load more */}
          {hasMore && (
            <div className="flex justify-center pb-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleLoadMore}
                disabled={loadingMore}
                aria-label="Load more notifications"
              >
                {loadingMore ? (
                  <>
                    <Loader2
                      className="mr-2 h-4 w-4 animate-spin"
                      aria-hidden="true"
                    />
                    Loading…
                  </>
                ) : (
                  "Load more"
                )}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Notification list with day grouping ───────────────────────────────────────

function NotificationList({ items }: { items: NotificationItem[] }) {
  const groups = groupByDay(items);

  return (
    <div
      className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 divide-y divide-zinc-100 dark:divide-zinc-800"
      role="feed"
      aria-label="Notification history"
    >
      {groups.map((group) => (
        <section key={group.label} aria-label={group.label}>
          {/* Day header */}
          <div className="sticky top-0 z-10 bg-zinc-50/90 dark:bg-zinc-900/90 backdrop-blur-sm px-4 py-2 border-b border-zinc-100 dark:border-zinc-800">
            <span className="text-xs font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
              {group.label}
            </span>
          </div>

          {/* Items for this day */}
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {group.items.map((item) => (
              <NotificationRow key={item.id} item={item} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

// ── Individual notification row ───────────────────────────────────────────────

function NotificationRow({ item }: { item: NotificationItem }) {
  const Icon = notifIcon(item.type);
  const isAlert = item.type === "alert";
  const isApproval = item.type === "approval";

  const iconBg = cn(
    "flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
    isAlert
      ? "bg-amber-100 dark:bg-amber-900/30"
      : isApproval
        ? "bg-emerald-100 dark:bg-emerald-900/30"
        : "bg-brand-100 dark:bg-brand-900/30"
  );

  const iconColor = cn(
    "h-4 w-4",
    isAlert
      ? "text-amber-600 dark:text-amber-400"
      : isApproval
        ? "text-emerald-600 dark:text-emerald-400"
        : "text-brand-600 dark:text-brand-400"
  );

  return (
    <li role="article">
      <Link
        href={item.href}
        className={cn(
          "flex items-start gap-3 px-4 py-3.5 transition-colors",
          "hover:bg-zinc-50 dark:hover:bg-zinc-800/60",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-500"
        )}
        aria-label={`${item.title}${item.subtitle ? ` — ${item.subtitle}` : ""}, ${formatDate(item.created_at)}`}
      >
        {/* Type icon */}
        <div className={iconBg} aria-hidden="true">
          <Icon className={iconColor} />
        </div>

        {/* Text content */}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium leading-snug text-zinc-900 dark:text-zinc-100">
            {item.title}
          </p>
          {item.subtitle && (
            <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400 leading-snug">
              {item.subtitle}
            </p>
          )}
        </div>

        {/* Timestamp */}
        <time
          dateTime={item.created_at}
          className="ml-2 shrink-0 text-xs text-zinc-400 dark:text-zinc-500 whitespace-nowrap pt-0.5"
        >
          {formatDate(item.created_at)}
        </time>
      </Link>
    </li>
  );
}

// ── Loading skeleton ──────────────────────────────────────────────────────────

function NotificationSkeleton() {
  return (
    <div
      className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 divide-y divide-zinc-100 dark:divide-zinc-800"
      aria-busy="true"
      aria-label="Loading notifications"
    >
      {/* Skeleton day header */}
      <div className="px-4 py-2">
        <Skeleton className="h-3 w-16" />
      </div>
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex items-start gap-3 px-4 py-3.5">
          <Skeleton className="h-9 w-9 shrink-0 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-3/5" />
            <Skeleton className="h-3 w-2/5" />
          </div>
          <Skeleton className="h-3 w-14 shrink-0 mt-0.5" />
        </div>
      ))}
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <BellRing
        className="mb-3 h-10 w-10 text-zinc-300 dark:text-zinc-600"
        aria-hidden="true"
      />
      <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">
        No notifications yet
      </h2>
      <p className="mt-1 text-sm text-zinc-400 dark:text-zinc-500 max-w-xs">
        Renewal alerts and approval requests will show up here.
      </p>
    </div>
  );
}

// ── Error state ───────────────────────────────────────────────────────────────

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
      <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">
        Failed to load notifications
      </h2>
      <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{message}</p>
      <Button size="sm" variant="outline" className="mt-4" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}
