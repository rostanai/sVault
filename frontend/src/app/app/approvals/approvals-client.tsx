"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getApprovals,
  createApproval,
  approveApproval,
  rejectApproval,
  type ApprovalRead,
  type ApprovalActionType,
  type ApprovalStatus,
} from "@/lib/api";
import { formatDate, formatINR, cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import {
  CheckSquare,
  Check,
  X,
  Plus,
  Clock,
  Loader2,
  AlertTriangle,
} from "lucide-react";

// ── Constants ──────────────────────────────────────────────────────────────

const ACTION_TYPES: { value: ApprovalActionType; label: string }[] = [
  { value: "renewal", label: "Renewal" },
  { value: "new_policy", label: "New Policy" },
  { value: "vendor_finalization", label: "Vendor Finalization" },
  { value: "high_value_premium", label: "High-Value Premium" },
  { value: "other", label: "Other" },
];

function humanizeActionType(type: string): string {
  const found = ACTION_TYPES.find((a) => a.value === type);
  if (found) return found.label;
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

const STATUS_FILTERS: { value: ApprovalStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "cancelled", label: "Cancelled" },
];

// ── Types ─────────────────────────────────────────────────────────────────

interface Props {
  token: string;
}

// Per-row action state
interface RowActionState {
  approving: boolean;
  rejecting: boolean;
}

// ── Main component ──────────────────────────────────────────────────────────

export default function ApprovalsClient({ token }: Props) {
  const [approvals, setApprovals] = useState<ApprovalRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<ApprovalStatus | "all">(
    "all"
  );

  // New request dialog
  const [newDialogOpen, setNewDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [newActionType, setNewActionType] =
    useState<ApprovalActionType>("renewal");
  const [newEntityType, setNewEntityType] = useState("policy");
  const [newEntityId, setNewEntityId] = useState("");
  const [newAmountInr, setNewAmountInr] = useState("");

  // Confirm action dialog (approve/reject)
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [confirmMode, setConfirmMode] = useState<"approve" | "reject">(
    "approve"
  );
  const [confirmApprovalId, setConfirmApprovalId] = useState("");
  const [confirmReason, setConfirmReason] = useState("");
  const [confirmSubmitting, setConfirmSubmitting] = useState(false);

  // Per-row in-flight state (keyed by approval id)
  const [rowActions, setRowActions] = useState<
    Record<string, RowActionState>
  >({});

  const fetchApprovals = useCallback(() => {
    if (!token) return;
    setLoading(true);
    getApprovals(token, {
      status: statusFilter === "all" ? undefined : statusFilter,
      limit: 50,
    })
      .then((res) => {
        setApprovals(Array.isArray(res) ? res : []);
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token, statusFilter]);

  useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  // ── New request submit ──────────────────────────────────────────────────

  async function handleNewRequest(e: React.FormEvent) {
    e.preventDefault();
    if (!newEntityId.trim()) return;
    setSubmitting(true);
    try {
      await createApproval(token, {
        action_type: newActionType,
        entity_type: newEntityType.trim() || "policy",
        entity_id: newEntityId.trim(),
        amount_inr: newAmountInr.trim() || undefined,
      });
      toast.success("Approval request submitted.");
      setNewDialogOpen(false);
      resetNewForm();
      fetchApprovals();
    } catch {
      // apiFetch already showed a toast
    } finally {
      setSubmitting(false);
    }
  }

  function resetNewForm() {
    setNewActionType("renewal");
    setNewEntityType("policy");
    setNewEntityId("");
    setNewAmountInr("");
  }

  // ── Approve / reject via confirm dialog ────────────────────────────────

  function openConfirm(
    mode: "approve" | "reject",
    approvalId: string
  ) {
    setConfirmMode(mode);
    setConfirmApprovalId(approvalId);
    setConfirmReason("");
    setConfirmDialogOpen(true);
  }

  async function handleConfirmAction() {
    if (!confirmApprovalId) return;
    setConfirmSubmitting(true);
    setRowActions((prev) => ({
      ...prev,
      [confirmApprovalId]: {
        approving: confirmMode === "approve",
        rejecting: confirmMode === "reject",
      },
    }));
    try {
      if (confirmMode === "approve") {
        await approveApproval(
          token,
          confirmApprovalId,
          confirmReason.trim() || undefined
        );
        toast.success("Approval granted.");
      } else {
        await rejectApproval(
          token,
          confirmApprovalId,
          confirmReason.trim() || undefined
        );
        toast.success("Request rejected.");
      }
      setConfirmDialogOpen(false);
      fetchApprovals();
    } catch {
      // apiFetch already showed a toast
    } finally {
      setConfirmSubmitting(false);
      setRowActions((prev) => {
        const next = { ...prev };
        delete next[confirmApprovalId];
        return next;
      });
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <CheckSquare className="h-6 w-6 text-brand-600" />
            Approvals
          </h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">
            Review and sign off on renewals, new policies, and vendor decisions.
          </p>
        </div>

        {/* New request dialog trigger */}
        <Dialog
          open={newDialogOpen}
          onOpenChange={(v) => {
            setNewDialogOpen(v);
            if (!v) resetNewForm();
          }}
        >
          <DialogTrigger asChild>
            <Button size="sm" className="shrink-0">
              <Plus className="mr-1.5 h-4 w-4" />
              New request
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>New Approval Request</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleNewRequest} className="space-y-4 py-2">
              <div className="space-y-1.5">
                <Label htmlFor="newActionType">Action type *</Label>
                <Select
                  value={newActionType}
                  onValueChange={(v) =>
                    setNewActionType(v as ApprovalActionType)
                  }
                  disabled={submitting}
                >
                  <SelectTrigger id="newActionType">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ACTION_TYPES.map((a) => (
                      <SelectItem key={a.value} value={a.value}>
                        {a.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="newEntityType">Entity type *</Label>
                  <Input
                    id="newEntityType"
                    placeholder="policy"
                    value={newEntityType}
                    onChange={(e) => setNewEntityType(e.target.value)}
                    disabled={submitting}
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="newAmountInr">Amount (₹)</Label>
                  <Input
                    id="newAmountInr"
                    type="number"
                    placeholder="Optional"
                    value={newAmountInr}
                    onChange={(e) => setNewAmountInr(e.target.value)}
                    disabled={submitting}
                    min="0"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="newEntityId">Entity ID *</Label>
                <Input
                  id="newEntityId"
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  value={newEntityId}
                  onChange={(e) => setNewEntityId(e.target.value)}
                  disabled={submitting}
                  required
                />
                <p className="text-xs text-zinc-400">
                  UUID of the related policy or record.
                </p>
              </div>

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setNewDialogOpen(false)}
                  disabled={submitting}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={submitting || !newEntityId.trim()}
                >
                  {submitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Submitting…
                    </>
                  ) : (
                    "Submit request"
                  )}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
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
        <ErrorState message={error} onRetry={fetchApprovals} />
      ) : approvals.length === 0 ? (
        <EmptyState
          hasFilter={statusFilter !== "all"}
          onNewRequest={() => setNewDialogOpen(true)}
        />
      ) : (
        <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Action</TableHead>
                <TableHead>Entity</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Requested</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {approvals.map((approval) => {
                const rowState = rowActions[approval.id];
                const isInFlight =
                  rowState?.approving || rowState?.rejecting;

                return (
                  <TableRow key={approval.id}>
                    {/* Action type */}
                    <TableCell>
                      <span className="font-medium">
                        {humanizeActionType(approval.action_type)}
                      </span>
                    </TableCell>

                    {/* Entity */}
                    <TableCell>
                      <div className="font-medium capitalize">
                        {approval.entity_type}
                      </div>
                      <div className="text-xs text-zinc-400 font-mono">
                        {approval.entity_id.slice(0, 8)}…
                      </div>
                    </TableCell>

                    {/* Amount */}
                    <TableCell className="tabular-nums">
                      {formatINR(approval.amount_inr)}
                    </TableCell>

                    {/* Status badge */}
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <Badge variant={statusVariant(approval.status)}>
                          {approval.status.charAt(0).toUpperCase() +
                            approval.status.slice(1)}
                        </Badge>
                        {approval.is_self_approval && (
                          <Badge
                            variant="outline"
                            className="text-xs w-fit border-zinc-300 dark:border-zinc-600 text-zinc-500 dark:text-zinc-400"
                          >
                            self-approved
                          </Badge>
                        )}
                      </div>
                    </TableCell>

                    {/* Requested date */}
                    <TableCell className="text-zinc-500 text-sm whitespace-nowrap">
                      {formatDate(approval.created_at)}
                    </TableCell>

                    {/* Actions column */}
                    <TableCell className="text-right">
                      {approval.status === "pending" ? (
                        <div className="flex items-center justify-end gap-2">
                          {isInFlight ? (
                            <Loader2 className="h-4 w-4 animate-spin text-zinc-400" />
                          ) : (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 px-2.5 text-xs text-emerald-600 border-emerald-200 hover:bg-emerald-50 dark:border-emerald-800 dark:text-emerald-400 dark:hover:bg-emerald-900/20"
                                onClick={() =>
                                  openConfirm("approve", approval.id)
                                }
                                aria-label={`Approve request ${approval.id}`}
                              >
                                <Check className="mr-1 h-3.5 w-3.5" />
                                Approve
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 px-2.5 text-xs text-red-600 border-red-200 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/20"
                                onClick={() =>
                                  openConfirm("reject", approval.id)
                                }
                                aria-label={`Reject request ${approval.id}`}
                              >
                                <X className="mr-1 h-3.5 w-3.5" />
                                Reject
                              </Button>
                            </>
                          )}
                        </div>
                      ) : (
                        <div className="flex flex-col items-end gap-1">
                          <div className="flex items-center gap-1 text-xs text-zinc-400">
                            <Clock className="h-3 w-3 shrink-0" />
                            {formatDate(approval.decided_at)}
                          </div>
                          {approval.reason && (
                            <p
                              className="text-xs text-zinc-400 max-w-[160px] text-right truncate"
                              title={approval.reason}
                            >
                              {approval.reason}
                            </p>
                          )}
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

      {/* Confirm approve / reject dialog */}
      <Dialog open={confirmDialogOpen} onOpenChange={setConfirmDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>
              {confirmMode === "approve"
                ? "Approve this request?"
                : "Reject this request?"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="confirmReason">
                Reason{" "}
                <span className="text-zinc-400 font-normal">(optional)</span>
              </Label>
              <textarea
                id="confirmReason"
                rows={3}
                placeholder="Add a note for the requester…"
                value={confirmReason}
                onChange={(e) => setConfirmReason(e.target.value)}
                disabled={confirmSubmitting}
                className={cn(
                  "w-full rounded-md border border-zinc-200 bg-transparent px-3 py-2 text-sm",
                  "placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-brand-600",
                  "dark:border-zinc-800 dark:text-zinc-100 dark:placeholder:text-zinc-600",
                  "resize-none"
                )}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirmDialogOpen(false)}
              disabled={confirmSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant={confirmMode === "approve" ? "default" : "destructive"}
              onClick={handleConfirmAction}
              disabled={confirmSubmitting}
              className={
                confirmMode === "approve"
                  ? "bg-brand-600 hover:bg-brand-600/90"
                  : undefined
              }
            >
              {confirmSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {confirmMode === "approve" ? "Approving…" : "Rejecting…"}
                </>
              ) : confirmMode === "approve" ? (
                <>
                  <Check className="mr-1.5 h-4 w-4" />
                  Approve
                </>
              ) : (
                <>
                  <X className="mr-1.5 h-4 w-4" />
                  Reject
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ── Status badge variant ──────────────────────────────────────────────────

function statusVariant(
  status: string
): "warning" | "success" | "destructive" | "secondary" {
  if (status === "pending") return "warning";
  if (status === "approved") return "success";
  if (status === "rejected") return "destructive";
  return "secondary"; // cancelled + anything else
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

function EmptyState({
  hasFilter,
  onNewRequest,
}: {
  hasFilter: boolean;
  onNewRequest: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <CheckSquare className="mb-3 h-10 w-10 text-zinc-300" />
      <h3 className="font-semibold">
        {hasFilter ? "No matching requests" : "No approval requests yet"}
      </h3>
      <p className="mt-1 text-sm text-zinc-400">
        {hasFilter
          ? "Try selecting a different status filter."
          : "Create a request when a renewal, policy, or vendor needs sign-off."}
      </p>
      {!hasFilter && (
        <Button
          size="sm"
          className="mt-4"
          onClick={onNewRequest}
        >
          <Plus className="mr-1.5 h-4 w-4" />
          New request
        </Button>
      )}
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
      <h3 className="font-semibold">Failed to load approvals</h3>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
      <Button size="sm" variant="outline" className="mt-4" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}
