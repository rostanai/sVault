"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  getClaim,
  updateClaim,
  getClaimEvents,
  type ClaimRead,
  type ClaimEvent,
  type ClaimStatus,
  type ClaimUpdate,
} from "@/lib/api";
import { formatDate, formatINR, cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  ArrowLeft,
  AlertTriangle,
  Clock,
  Loader2,
  FileWarning,
  Pencil,
} from "lucide-react";
import { toast } from "sonner";

// ── Status helpers ─────────────────────────────────────────────────
const CLAIM_STATUSES: { value: ClaimStatus; label: string }[] = [
  { value: "draft", label: "Draft" },
  { value: "reported", label: "Reported" },
  { value: "under_review", label: "Under Review" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "settled", label: "Settled" },
  { value: "closed", label: "Closed" },
];

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

function humanizeEventType(eventType: string): string {
  return eventType
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

// ── Props ────────────────────────────────────────────────────
interface Props {
  id: string;
  token: string;
}

// ── Edit form state ───────────────────────────────────────────
interface EditFormState {
  claim_number: string;
  claim_amount_inr: string;
  incident_date: string;
  description: string;
}

// ── Main component ───────────────────────────────────────────
export default function ClaimDetailClient({ id, token }: Props) {
  const [claim, setClaim] = useState<ClaimRead | null>(null);
  const [events, setEvents] = useState<ClaimEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Update card state
  const [updateStatus, setUpdateStatus] = useState<ClaimStatus | "">("");
  const [approvedAmount, setApprovedAmount] = useState("");
  const [updateNote, setUpdateNote] = useState("");
  const [updating, setUpdating] = useState(false);

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editForm, setEditForm] = useState<EditFormState>({
    claim_number: "",
    claim_amount_inr: "",
    incident_date: "",
    description: "",
  });
  const [editSubmitting, setEditSubmitting] = useState(false);

  // ── Fetch claim + events ───────────────────────────────────
  const fetchClaim = useCallback(() => {
    if (!token) return;
    setLoading(true);
    getClaim(token, id)
      .then((c) => {
        setClaim(c);
        setUpdateStatus(c.status as ClaimStatus);
        setApprovedAmount(c.approved_amount_inr ?? "");
        setError(null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token, id]);

  const fetchEvents = useCallback(() => {
    if (!token) return;
    setEventsLoading(true);
    getClaimEvents(token, id)
      .then((evts) => {
        // Sort newest-first
        const sorted = [...evts].sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
        setEvents(sorted);
      })
      .catch(() => {
        // Non-fatal — timeline simply won't populate
      })
      .finally(() => setEventsLoading(false));
  }, [token, id]);

  useEffect(() => {
    fetchClaim();
    fetchEvents();
  }, [fetchClaim, fetchEvents]);

  // ── Update claim (status + approved_amount + note) ────────────────────
  async function handleUpdate() {
    if (!claim) return;
    const payload: ClaimUpdate = {};
    if (updateStatus && updateStatus !== claim.status) {
      payload.status = updateStatus as ClaimStatus;
    }
    if (approvedAmount.trim() !== (claim.approved_amount_inr ?? "")) {
      payload.approved_amount_inr = approvedAmount.trim() || undefined;
    }
    if (updateNote.trim()) {
      payload.note = updateNote.trim();
    }
    if (Object.keys(payload).length === 0) {
      toast.info("No changes to save.");
      return;
    }
    setUpdating(true);
    try {
      const updated = await updateClaim(token, id, payload);
      setClaim(updated);
      setUpdateStatus(updated.status as ClaimStatus);
      setApprovedAmount(updated.approved_amount_inr ?? "");
      setUpdateNote("");
      toast.success("Claim updated.");
      fetchEvents();
    } catch {
      // apiFetch already toasted
    } finally {
      setUpdating(false);
    }
  }

  // ── Edit dialog ──────────────────────────────────────────
  function openEditDialog() {
    if (!claim) return;
    setEditForm({
      claim_number: claim.claim_number ?? "",
      claim_amount_inr: claim.claim_amount_inr ?? "",
      incident_date: claim.incident_date ?? "",
      description: claim.description ?? "",
    });
    setEditDialogOpen(true);
  }

  async function handleEditSave(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!claim) return;
    setEditSubmitting(true);
    try {
      const payload: ClaimUpdate = {};
      const trimmedClaimNumber = editForm.claim_number.trim();
      if (trimmedClaimNumber !== (claim.claim_number ?? "")) {
        payload.claim_number = trimmedClaimNumber || undefined;
      }
      if (editForm.claim_amount_inr.trim() !== (claim.claim_amount_inr ?? "")) {
        payload.claim_amount_inr = editForm.claim_amount_inr.trim() || undefined;
      }
      if (editForm.incident_date !== (claim.incident_date ?? "")) {
        payload.incident_date = editForm.incident_date || undefined;
      }
      if (editForm.description.trim() !== (claim.description ?? "")) {
        payload.description = editForm.description.trim() || undefined;
      }
      if (Object.keys(payload).length === 0) {
        setEditDialogOpen(false);
        return;
      }
      const updated = await updateClaim(token, id, payload);
      setClaim(updated);
      setEditDialogOpen(false);
      toast.success("Claim details updated.");
      fetchEvents();
    } catch {
      // apiFetch already toasted
    } finally {
      setEditSubmitting(false);
    }
  }

  // ── Loading / error ───────────────────────────────────────
  if (loading) return <DetailSkeleton />;
  if (error) return <ErrorState message={error} onRetry={fetchClaim} />;
  if (!claim) return null;

  const settledOrClosed =
    claim.status === "settled" || claim.status === "closed";

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Back link */}
      <div>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/app/claims" className="flex items-center gap-1.5">
            <ArrowLeft className="h-4 w-4" />
            Back to Claims
          </Link>
        </Button>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <FileWarning className="h-6 w-6 text-brand-600 shrink-0" />
            {claim.claim_number ?? `Claim ${claim.id.slice(0, 8)}…`}
          </h2>
          <div className="flex items-center gap-2 flex-wrap">
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
            {claim.policy_title && (
              <Link
                href={`/app/policies/${claim.policy_id}`}
                className="text-sm text-brand-600 hover:underline dark:text-brand-400"
              >
                {claim.policy_title}
              </Link>
            )}
          </div>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={openEditDialog}
          aria-label="Edit claim details"
          className="h-7 px-2.5 text-xs shrink-0"
        >
          <Pencil className="mr-1 h-3.5 w-3.5" />
          Edit
        </Button>
      </div>

      {/* Edit dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Pencil className="h-4 w-4 text-brand-600" />
              Edit claim
            </DialogTitle>
          </DialogHeader>

          <form
            id="edit-claim-form"
            onSubmit={handleEditSave}
            noValidate
            className="space-y-4 pt-1"
          >
            {/* Claim number */}
            <div className="space-y-1.5">
              <Label htmlFor="edit-claim-number" className="text-xs font-medium">
                Claim number
              </Label>
              <Input
                id="edit-claim-number"
                type="text"
                placeholder="e.g. CLM-2026-001"
                value={editForm.claim_number}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, claim_number: e.target.value }))
                }
                className="h-8 text-sm"
                disabled={editSubmitting}
              />
            </div>

            {/* Claim amount */}
            <div className="space-y-1.5">
              <Label htmlFor="edit-claim-amount" className="text-xs font-medium">
                Claim amount (INR)
              </Label>
              <Input
                id="edit-claim-amount"
                type="text"
                inputMode="decimal"
                placeholder="e.g. 500000"
                value={editForm.claim_amount_inr}
                onChange={(e) =>
                  setEditForm((f) => ({
                    ...f,
                    claim_amount_inr: e.target.value,
                  }))
                }
                className="h-8 text-sm"
                disabled={editSubmitting}
              />
            </div>

            {/* Incident date */}
            <div className="space-y-1.5">
              <Label htmlFor="edit-incident-date" className="text-xs font-medium">
                Incident date
              </Label>
              <Input
                id="edit-incident-date"
                type="date"
                value={editForm.incident_date}
                onChange={(e) =>
                  setEditForm((f) => ({
                    ...f,
                    incident_date: e.target.value,
                  }))
                }
                className="h-8 text-sm"
                disabled={editSubmitting}
              />
            </div>

            {/* Description */}
            <div className="space-y-1.5">
              <Label htmlFor="edit-description" className="text-xs font-medium">
                Description
              </Label>
              <textarea
                id="edit-description"
                rows={3}
                placeholder="Describe the incident or claim details…"
                value={editForm.description}
                onChange={(e) =>
                  setEditForm((f) => ({
                    ...f,
                    description: e.target.value,
                  }))
                }
                disabled={editSubmitting}
                className={cn(
                  "w-full rounded-md border border-zinc-200 bg-transparent px-3 py-2 text-sm",
                  "placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-brand-600",
                  "dark:border-zinc-800 dark:text-zinc-100 dark:placeholder:text-zinc-600",
                  "resize-none"
                )}
              />
            </div>
          </form>

          <DialogFooter className="flex gap-2 sm:justify-end pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setEditDialogOpen(false)}
              disabled={editSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form="edit-claim-form"
              size="sm"
              disabled={editSubmitting}
              className="bg-brand-600 hover:bg-brand-600/90 text-white"
            >
              {editSubmitting ? (
                <>
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                <>
                  <Pencil className="mr-1.5 h-4 w-4" />
                  Save changes
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Details card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Claim Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                Claim Amount
              </dt>
              <dd className="mt-1 text-sm font-medium">
                {formatINR(claim.claim_amount_inr)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                Approved Amount
              </dt>
              <dd className="mt-1 text-sm font-medium">
                {formatINR(claim.approved_amount_inr)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                Incident Date
              </dt>
              <dd className="mt-1 text-sm font-medium">
                {formatDate(claim.incident_date)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                Reported Date
              </dt>
              <dd className="mt-1 text-sm font-medium">
                {formatDate(claim.reported_date)}
              </dd>
            </div>
            {claim.description && (
              <div className="sm:col-span-2">
                <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  Description
                </dt>
                <dd className="mt-1 text-sm font-medium whitespace-pre-wrap">
                  {claim.description}
                </dd>
              </div>
            )}
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                Created
              </dt>
              <dd className="mt-1 text-sm font-medium">
                {formatDate(claim.created_at)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                Last Updated
              </dt>
              <dd className="mt-1 text-sm font-medium">
                {formatDate(claim.updated_at)}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* Update card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Update Claim</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Status select */}
            <div className="space-y-1.5">
              <Label htmlFor="update-status" className="text-xs font-medium">
                Status
              </Label>
              <Select
                value={updateStatus}
                onValueChange={(v) => setUpdateStatus(v as ClaimStatus)}
                disabled={updating || settledOrClosed}
              >
                <SelectTrigger id="update-status" className="h-9 text-sm">
                  <SelectValue placeholder="Select status" />
                </SelectTrigger>
                <SelectContent>
                  {CLAIM_STATUSES.map(({ value, label }) => (
                    <SelectItem key={value} value={value} className="text-sm">
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Approved amount */}
            <div className="space-y-1.5">
              <Label
                htmlFor="update-approved-amount"
                className="text-xs font-medium"
              >
                Approved Amount (INR){" "}
                <span className="text-zinc-400 font-normal">(optional)</span>
              </Label>
              <Input
                id="update-approved-amount"
                type="text"
                inputMode="decimal"
                placeholder="e.g. 450000"
                value={approvedAmount}
                onChange={(e) => setApprovedAmount(e.target.value)}
                disabled={updating || settledOrClosed}
                className="h-9 text-sm"
              />
            </div>

            {/* Note textarea */}
            <div className="space-y-1.5">
              <Label htmlFor="update-note" className="text-xs font-medium">
                Note{" "}
                <span className="text-zinc-400 font-normal">(optional)</span>
              </Label>
              <textarea
                id="update-note"
                rows={2}
                placeholder="Add a note about this update…"
                value={updateNote}
                onChange={(e) => setUpdateNote(e.target.value)}
                disabled={updating || settledOrClosed}
                className={cn(
                  "w-full rounded-md border border-zinc-200 bg-transparent px-3 py-2 text-sm",
                  "placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-brand-600",
                  "dark:border-zinc-800 dark:text-zinc-100 dark:placeholder:text-zinc-600",
                  "resize-none"
                )}
              />
            </div>

            {settledOrClosed ? (
              <p className="text-xs text-zinc-400">
                This claim is {claimStatusLabel(claim.status).toLowerCase()} and
                cannot be further updated.
              </p>
            ) : (
              <Button
                size="sm"
                disabled={updating}
                onClick={handleUpdate}
                className="bg-brand-600 hover:bg-brand-600/90 text-white"
              >
                {updating ? (
                  <>
                    <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    Updating…
                  </>
                ) : (
                  "Update claim"
                )}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Timeline card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Clock className="h-4 w-4 text-brand-600" />
            Timeline
          </CardTitle>
        </CardHeader>
        <CardContent>
          {eventsLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex gap-3">
                  <Skeleton className="h-4 w-4 rounded-full mt-0.5 shrink-0" />
                  <div className="flex-1 space-y-1.5">
                    <Skeleton className="h-3 w-32" />
                    <Skeleton className="h-3 w-48" />
                  </div>
                </div>
              ))}
            </div>
          ) : events.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Clock className="mb-2 h-7 w-7 text-zinc-300" />
              <p className="text-sm text-zinc-500">No events recorded yet.</p>
            </div>
          ) : (
            <ol
              aria-label="Claim event timeline"
              className="relative border-l border-zinc-200 dark:border-zinc-800 space-y-0"
            >
              {events.map((event, idx) => (
                <li
                  key={event.id}
                  className={cn(
                    "ml-4 pb-5",
                    idx === events.length - 1 ? "pb-0" : ""
                  )}
                >
                  {/* Timeline dot */}
                  <span
                    aria-hidden="true"
                    className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border border-white bg-zinc-300 dark:border-zinc-900 dark:bg-zinc-600"
                  />

                  {/* Event type + timestamp */}
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mb-0.5">
                    <span className="text-sm font-semibold">
                      {humanizeEventType(event.event_type)}
                    </span>
                    <span className="flex items-center gap-1 text-xs text-zinc-400">
                      <Clock className="h-3 w-3 shrink-0" />
                      {formatDate(event.created_at)}
                    </span>
                  </div>

                  {/* Status transition */}
                  {event.from_status && event.to_status && (
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-0.5">
                      <span className="inline-flex items-center gap-1.5">
                        <Badge
                          variant={claimStatusVariant(event.from_status)}
                          className="text-xs py-0 h-5"
                        >
                          {claimStatusLabel(event.from_status)}
                        </Badge>
                        <span aria-hidden="true">→</span>
                        <Badge
                          variant={claimStatusVariant(event.to_status)}
                          className="text-xs py-0 h-5"
                        >
                          {claimStatusLabel(event.to_status)}
                        </Badge>
                      </span>
                    </p>
                  )}

                  {/* Note */}
                  {event.note && (
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 italic">
                      &ldquo;{event.note}&rdquo;
                    </p>
                  )}
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ── Skeleton ─────────────────────────────────────────────────
function DetailSkeleton() {
  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <Skeleton className="h-8 w-24" />
      <div className="space-y-2">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-5 w-36" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-28" />
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="space-y-1">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-4 w-28" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-28" />
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-8 w-28" />
        </CardContent>
      </Card>
    </div>
  );
}

// ── Error state ─────────────────────────────────────────────
function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="space-y-4 max-w-4xl mx-auto">
      <Button variant="ghost" size="sm" asChild>
        <Link href="/app/claims" className="flex items-center gap-1.5">
          <ArrowLeft className="h-4 w-4" />
          Back to Claims
        </Link>
      </Button>
      <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <AlertTriangle className="mb-3 h-10 w-10 text-red-400" />
        <h3 className="font-semibold">Failed to load claim</h3>
        <p className="mt-1 text-sm text-zinc-500">{message}</p>
        <Button size="sm" variant="outline" className="mt-4" onClick={onRetry}>
          Retry
        </Button>
      </div>
    </div>
  );
}
