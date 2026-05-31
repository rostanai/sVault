"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getAlerts,
  getPolicies,
  acknowledgeAlert,
  snoozeAlert,
  type AlertRead,
  type PolicyRead,
} from "@/lib/api";
import { formatDate, cn } from "@/lib/utils";
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";
import {
  Bell,
  BellOff,
  Check,
  ChevronDown,
  Clock,
  Loader2,
  AlertTriangle,
  MessageSquare,
  Mail,
  Phone,
  Send,
} from "lucide-react";

interface Props {
  token: string;
}

type AlertStatusFilter = "all" | "scheduled" | "sent" | "acknowledged" | "failed";

interface PolicyMeta {
  title: string;
  category: string;
}

const STATUS_FILTERS: { value: AlertStatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "scheduled", label: "Scheduled" },
  { value: "sent", label: "Sent" },
  { value: "acknowledged", label: "Acknowledged" },
  { value: "failed", label: "Failed" },
];

function humanizeChannel(channel: string): string {
  const map: Record<string, string> = {
    whatsapp: "WhatsApp",
    email: "Email",
    sms: "SMS",
    telegram: "Telegram",
  };
  return map[channel] ?? channel.charAt(0).toUpperCase() + channel.slice(1);
}

function ChannelIcon({ channel }: { channel: string }) {
  const cls = "h-3.5 w-3.5 shrink-0";
  if (channel === "whatsapp") return <MessageSquare className={cls} />;
  if (channel === "email") return <Mail className={cls} />;
  if (channel === "sms") return <Phone className={cls} />;
  if (channel === "telegram") return <Send className={cls} />;
  return <Bell className={cls} />;
}

function alertStatusVariant(
  status: string
): "secondary" | "success" | "outline" | "destructive" | "default" {
  if (status === "scheduled") return "secondary";
  if (status === "sent") return "success";
  if (status === "acknowledged") return "outline";
  if (status === "failed") return "destructive";
  return "secondary";
}

export default function AlertsClient({ token }: Props) {
  const [alerts, setAlerts] = useState<AlertRead[]>([]);
  const [policyMap, setPolicyMap] = useState<Map<string, PolicyMeta>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<AlertStatusFilter>("all");
  const [ackingId, setAckingId] = useState<string | null>(null);
  const [snoozingId, setSnoozingId] = useState<string | null>(null);

  const fetchData = useCallback(() => {
    if (!token) return;
    setLoading(true);
    setError(null);

    Promise.all([
      getAlerts(token, { limit: 100 }),
      getPolicies(token),
    ])
      .then(([alertsRes, policiesRes]) => {
        setAlerts(Array.isArray(alertsRes) ? alertsRes : []);

        const map = new Map<string, PolicyMeta>();
        const policies: PolicyRead[] = Array.isArray(policiesRes)
          ? policiesRes
          : [];
        for (const p of policies) {
          map.set(p.id, { title: p.title, category: p.category });
        }
        setPolicyMap(map);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const displayed =
    statusFilter === "all"
      ? alerts
      : alerts.filter((a) => a.status === statusFilter);

  async function handleAcknowledge(alertId: string) {
    setAckingId(alertId);
    try {
      const updated = await acknowledgeAlert(token, alertId);
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === alertId
            ? {
                ...a,
                status: updated.status,
                acknowledged_at: new Date().toISOString(),
              }
            : a
        )
      );
      toast.success("Alert acknowledged.");
    } catch {
      // apiFetch already toasted
    } finally {
      setAckingId(null);
    }
  }

  async function handleSnooze(alertId: string, days: number) {
    setSnoozingId(alertId);
    try {
      const updated = await snoozeAlert(token, alertId, days);
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === alertId
            ? { ...a, status: updated.status, scheduled_for: updated.scheduled_for }
            : a
        )
      );
      toast.success(`Snoozed ${days} day${days === 1 ? "" : "s"}.`);
    } catch {
      // apiFetch already toasted
    } finally {
      setSnoozingId(null);
    }
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Bell className="h-6 w-6 text-brand-600" />
          Renewal Alerts
        </h2>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">
          Multi-channel reminders so you never miss a policy renewal.
        </p>
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

      {/* Content */}
      {loading ? (
        <TableSkeleton />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchData} />
      ) : displayed.length === 0 ? (
        <EmptyState hasFilter={statusFilter !== "all"} />
      ) : (
        <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Policy</TableHead>
                <TableHead>Channel</TableHead>
                <TableHead>Lead time</TableHead>
                <TableHead>Scheduled for</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {displayed.map((alert) => {
                const meta = policyMap.get(alert.policy_id);
                const isAcking = ackingId === alert.id;
                const isSnoozing = snoozingId === alert.id;
                const isBusy = isAcking || isSnoozing;

                return (
                  <TableRow key={alert.id}>
                    {/* Policy */}
                    <TableCell>
                      <div className="font-medium">
                        {meta?.title ?? (
                          <span className="font-mono text-xs text-zinc-400">
                            {alert.policy_id.slice(0, 8)}…
                          </span>
                        )}
                      </div>
                      {meta?.category && (
                        <div className="text-xs text-zinc-400 mt-0.5 capitalize">
                          {meta.category.replace(/_/g, " ")}
                        </div>
                      )}
                    </TableCell>

                    {/* Channel */}
                    <TableCell>
                      <div className="flex items-center gap-1.5 text-sm">
                        <ChannelIcon channel={alert.channel} />
                        {humanizeChannel(alert.channel)}
                      </div>
                    </TableCell>

                    {/* Lead time */}
                    <TableCell className="tabular-nums text-sm">
                      {alert.lead_day}d before
                    </TableCell>

                    {/* Scheduled for */}
                    <TableCell className="text-sm text-zinc-500 whitespace-nowrap">
                      {formatDate(alert.scheduled_for)}
                    </TableCell>

                    {/* Status */}
                    <TableCell>
                      <Badge
                        variant={alertStatusVariant(alert.status)}
                        className={cn(
                          alert.status === "acknowledged" &&
                            "flex items-center gap-1 w-fit border-zinc-300 dark:border-zinc-600 text-zinc-600 dark:text-zinc-300"
                        )}
                      >
                        {alert.status === "acknowledged" && (
                          <Check className="h-3 w-3 shrink-0" />
                        )}
                        {alert.status.charAt(0).toUpperCase() +
                          alert.status.slice(1)}
                      </Badge>
                    </TableCell>

                    {/* Actions */}
                    <TableCell className="text-right">
                      {alert.status !== "acknowledged" ? (
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Acknowledge */}
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={isBusy}
                            onClick={() => handleAcknowledge(alert.id)}
                            aria-label={`Acknowledge alert for policy ${meta?.title ?? alert.policy_id}`}
                            className="h-7 px-2.5 text-xs text-emerald-600 border-emerald-200 hover:bg-emerald-50 dark:border-emerald-800 dark:text-emerald-400 dark:hover:bg-emerald-900/20"
                          >
                            {isAcking ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <>
                                <Check className="mr-1 h-3.5 w-3.5" />
                                Acknowledge
                              </>
                            )}
                          </Button>

                          {/* Snooze */}
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={isBusy}
                                aria-label={`Snooze alert for policy ${meta?.title ?? alert.policy_id}`}
                                className="h-7 px-2.5 text-xs text-zinc-600 border-zinc-200 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800"
                              >
                                {isSnoozing ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <>
                                    <Clock className="mr-1 h-3.5 w-3.5" />
                                    Snooze
                                    <ChevronDown className="ml-1 h-3 w-3 opacity-60" />
                                  </>
                                )}
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-36">
                              {([1, 3, 7] as const).map((days) => (
                                <DropdownMenuItem
                                  key={days}
                                  onClick={() => handleSnooze(alert.id, days)}
                                  className="text-sm cursor-pointer"
                                >
                                  <Clock className="mr-2 h-3.5 w-3.5 text-zinc-400" />
                                  {days} day{days === 1 ? "" : "s"}
                                </DropdownMenuItem>
                              ))}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      ) : (
                        <div className="flex items-center justify-end gap-1 text-xs text-zinc-400">
                          <Check className="h-3 w-3 shrink-0" />
                          {formatDate(alert.acknowledged_at)}
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

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

function EmptyState({ hasFilter }: { hasFilter: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      {hasFilter ? (
        <BellOff className="mb-3 h-10 w-10 text-zinc-300" />
      ) : (
        <Bell className="mb-3 h-10 w-10 text-zinc-300" />
      )}
      <h3 className="font-semibold">
        {hasFilter ? "No matching alerts" : "No alerts yet"}
      </h3>
      <p className="mt-1 text-sm text-zinc-400 max-w-sm">
        {hasFilter
          ? "Try selecting a different status filter."
          : "Alerts appear here as policy renewal dates approach. Configure alert schedules on individual policies."}
      </p>
    </div>
  );
}

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
      <h3 className="font-semibold">Failed to load alerts</h3>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
      <Button size="sm" variant="outline" className="mt-4" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}
