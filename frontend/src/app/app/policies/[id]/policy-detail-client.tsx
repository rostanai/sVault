"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getPolicy,
  deletePolicy,
  listDocuments,
  getDocumentUploadUrl,
  uploadFileToStorage,
  recordDocument,
  deleteDocument,
  ingestDocument,
  getAlertRule,
  setAlertRule,
  markPolicyRenewed,
  renewPolicy,
  updatePolicy,
  getInstallments,
  addInstallment,
  markInstallmentPaid,
  deleteInstallment,
  type PolicyRead,
  type PolicyUpdate,
  type DocumentRead,
  type AlertChannel,
  type AlertRuleRead,
  type RenewPolicyRequest,
  type Installment,
  type InstallmentCreate,
} from "@/lib/api";
import {
  formatDate,
  formatINR,
  daysLeftVariant,
  categorylabel,
  statusLabel,
  cn,
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
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowLeft,
  AlertTriangle,
  CheckCircle,
  Upload,
  Loader2,
  FileText,
  Download,
  Trash2,
  Paperclip,
  Sparkles,
  Bell,
  MessageSquare,
  Mail,
  Phone,
  Send,
  RotateCw,
  Plus,
  IndianRupee,
  Wallet,
  Pencil,
  SlidersHorizontal,
} from "lucide-react";
import { toast } from "sonner";

const MAX_BYTES = 20 * 1024 * 1024; // 20 MB

// Status options for the Edit dialog
const POLICY_STATUSES: { value: string; label: string }[] = [
  { value: "draft", label: "Draft" },
  { value: "pending_approval", label: "Pending Approval" },
  { value: "active", label: "Active" },
  { value: "expiring", label: "Expiring" },
  { value: "lapsed", label: "Lapsed" },
  { value: "renewed", label: "Renewed" },
  { value: "cancelled", label: "Cancelled" },
];
const ALLOWED_TYPES = [
  "application/pdf",
  "image/png",
  "image/jpeg",
  "image/webp",
];
const ALLOWED_EXTS = ".pdf,.png,.jpg,.jpeg,.webp";

function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface Props {
  id: string;
  token: string;
}

/** Adds one year to an ISO date string, returning an ISO date string.
 *  Returns an empty string if the input is null/undefined/unparseable. */
function addOneYear(isoDate: string | null | undefined): string {
  if (!isoDate) return "";
  const d = new Date(isoDate);
  if (isNaN(d.getTime())) return "";
  d.setFullYear(d.getFullYear() + 1);
  return d.toISOString().slice(0, 10);
}

export default function PolicyDetailClient({ id, token }: Props) {
  const router = useRouter();
  const [policy, setPolicy] = useState<PolicyRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [renewConfirmOpen, setRenewConfirmOpen] = useState(false);
  const [markingRenewed, setMarkingRenewed] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deletingPolicy, setDeletingPolicy] = useState(false);

  // Renew-policy dialog state
  const [renewDialogOpen, setRenewDialogOpen] = useState(false);
  const [renewSubmitting, setRenewSubmitting] = useState(false);
  const [renewForm, setRenewForm] = useState<RenewPolicyRequest>({
    expiry_date: "",
    inception_date: "",
    renewal_date: "",
    premium_inr: "",
    gst_inr: "",
    sum_insured_inr: "",
    policy_number: "",
  });
  const [renewExpiryError, setRenewExpiryError] = useState<string | null>(null);

  // Edit-policy dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editForm, setEditForm] = useState<PolicyUpdate>({});

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

  async function handleMarkRenewed() {
    setMarkingRenewed(true);
    try {
      const updated = await markPolicyRenewed(token, id);
      setPolicy(updated);
      setRenewConfirmOpen(false);
      toast.success("Policy marked as renewed.");
    } catch {
      // apiFetch already toasted
    } finally {
      setMarkingRenewed(false);
    }
  }

  async function handleDeletePolicy() {
    setDeletingPolicy(true);
    try {
      await deletePolicy(token, id);
      toast.success("Policy deleted.");
      router.push("/app/policies");
    } catch {
      // apiFetch already toasted (403 if the role can't delete, etc.)
      setDeletingPolicy(false);
      setDeleteConfirmOpen(false);
    }
  }

  function openRenewDialog() {
    if (!policy) return;
    setRenewForm({
      expiry_date: addOneYear(policy.expiry_date),
      inception_date: policy.expiry_date ?? "",
      renewal_date: "",
      premium_inr: policy.premium_inr ?? "",
      gst_inr: policy.gst_inr ?? "",
      sum_insured_inr: policy.sum_insured_inr ?? "",
      policy_number: policy.policy_number ?? "",
    });
    setRenewExpiryError(null);
    setRenewDialogOpen(true);
  }

  async function handleRenewPolicy(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!renewForm.expiry_date) {
      setRenewExpiryError("Expiry date is required.");
      return;
    }
    setRenewExpiryError(null);
    setRenewSubmitting(true);
    try {
      const body: RenewPolicyRequest = {
        expiry_date: renewForm.expiry_date,
        ...(renewForm.inception_date ? { inception_date: renewForm.inception_date } : {}),
        ...(renewForm.renewal_date ? { renewal_date: renewForm.renewal_date } : {}),
        ...(renewForm.premium_inr ? { premium_inr: renewForm.premium_inr } : {}),
        ...(renewForm.gst_inr ? { gst_inr: renewForm.gst_inr } : {}),
        ...(renewForm.sum_insured_inr ? { sum_insured_inr: renewForm.sum_insured_inr } : {}),
        ...(renewForm.policy_number ? { policy_number: renewForm.policy_number } : {}),
      };
      const newPolicy = await renewPolicy(token, id, body);
      toast.success("Policy renewed — new term created.");
      setRenewDialogOpen(false);
      router.push(`/app/policies/${newPolicy.id}`);
    } catch {
      // apiFetch already toasted
    } finally {
      setRenewSubmitting(false);
    }
  }

  function openEditDialog() {
    if (!policy) return;
    setEditForm({
      title: policy.title,
      policy_number: policy.policy_number ?? "",
      sum_insured_inr: policy.sum_insured_inr ?? "",
      premium_inr: policy.premium_inr ?? "",
      gst_inr: policy.gst_inr ?? "",
      inception_date: policy.inception_date ?? "",
      expiry_date: policy.expiry_date ?? "",
      renewal_date: policy.renewal_date ?? "",
      status: policy.status,
    });
    setEditDialogOpen(true);
  }

  async function handleEditSave(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!policy) return;
    setEditSubmitting(true);
    try {
      // Build a body with only the standard (non-custom_fields) fields
      const body: PolicyUpdate = {
        ...(editForm.title !== undefined ? { title: editForm.title } : {}),
        ...(editForm.policy_number !== undefined ? { policy_number: editForm.policy_number || null } : {}),
        ...(editForm.sum_insured_inr !== undefined ? { sum_insured_inr: editForm.sum_insured_inr || null } : {}),
        ...(editForm.premium_inr !== undefined ? { premium_inr: editForm.premium_inr || null } : {}),
        ...(editForm.gst_inr !== undefined ? { gst_inr: editForm.gst_inr || null } : {}),
        ...(editForm.inception_date !== undefined ? { inception_date: editForm.inception_date || null } : {}),
        ...(editForm.expiry_date !== undefined ? { expiry_date: editForm.expiry_date || null } : {}),
        ...(editForm.renewal_date !== undefined ? { renewal_date: editForm.renewal_date || null } : {}),
        ...(editForm.status !== undefined ? { status: editForm.status } : {}),
      };
      const updated = await updatePolicy(token, id, body);
      setPolicy(updated);
      setEditDialogOpen(false);
      toast.success("Policy updated.");
    } catch {
      // apiFetch already toasted
    } finally {
      setEditSubmitting(false);
    }
  }

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
        <div className="flex flex-col items-end gap-2 shrink-0">
          <div className="flex items-center gap-2">
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
            <Button
              size="sm"
              variant="outline"
              onClick={openEditDialog}
              aria-label="Edit policy details"
              className="h-7 px-2.5 text-xs"
            >
              <Pencil className="mr-1 h-3.5 w-3.5" />
              Edit
            </Button>
            {policy.status !== "renewed" && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={openRenewDialog}
                  disabled={renewSubmitting}
                  aria-label="Renew this policy — create a new term"
                  className="h-7 px-2.5 text-xs text-brand-600 border-brand-600/40 hover:bg-brand-600/10 dark:text-brand-400 dark:border-brand-600/40 dark:hover:bg-brand-600/10"
                >
                  <RotateCw className="mr-1 h-3.5 w-3.5" />
                  Renew
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setRenewConfirmOpen(true)}
                  disabled={markingRenewed}
                  aria-label="Mark this policy as renewed"
                  className="h-7 px-2.5 text-xs text-brand-600 border-brand-600/40 hover:bg-brand-600/10 dark:text-brand-400 dark:border-brand-600/40 dark:hover:bg-brand-600/10"
                >
                  {markingRenewed ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <>
                      <CheckCircle className="mr-1 h-3.5 w-3.5" />
                      Mark renewed
                    </>
                  )}
                </Button>
              </>
            )}
            <Button
              size="sm"
              variant="outline"
              onClick={() => setDeleteConfirmOpen(true)}
              disabled={deletingPolicy}
              aria-label="Delete this policy"
              className="h-7 px-2.5 text-xs text-red-600 border-red-600/40 hover:bg-red-600/10 dark:text-red-400 dark:border-red-600/40 dark:hover:bg-red-600/10"
            >
              <Trash2 className="mr-1 h-3.5 w-3.5" />
              Delete
            </Button>
          </div>
          {daysLeft != null && (
            <Badge variant={daysLeftVariant(daysLeft)} className="text-xs">
              {daysLeft < 0
                ? `Expired ${Math.abs(daysLeft)}d ago`
                : `${daysLeft}d left`}
            </Badge>
          )}
        </div>
      </div>

      {/* Mark renewed confirm dialog */}
      <Dialog open={renewConfirmOpen} onOpenChange={setRenewConfirmOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Mark policy as renewed?</DialogTitle>
            <DialogDescription>
              This sets the status to &ldquo;Renewed&rdquo; and cancels all pending
              alerts for this policy. You can re-activate alerts at any time.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex gap-2 sm:justify-end">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setRenewConfirmOpen(false)}
              disabled={markingRenewed}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleMarkRenewed}
              disabled={markingRenewed}
              className="bg-brand-600 hover:bg-brand-600/90 text-white"
            >
              {markingRenewed ? (
                <>
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                <>
                  <CheckCircle className="mr-1.5 h-4 w-4" />
                  Confirm
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete policy confirm dialog */}
      <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete this policy?</DialogTitle>
            <DialogDescription>
              This permanently removes &ldquo;{policy.title}&rdquo; along with its
              documents, installments and alerts. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex gap-2 sm:justify-end">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDeleteConfirmOpen(false)}
              disabled={deletingPolicy}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleDeletePolicy}
              disabled={deletingPolicy}
              className="bg-red-600 hover:bg-red-600/90 text-white"
            >
              {deletingPolicy ? (
                <>
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  Deleting…
                </>
              ) : (
                <>
                  <Trash2 className="mr-1.5 h-4 w-4" />
                  Delete policy
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit policy dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Pencil className="h-4 w-4 text-brand-600" />
              Edit policy
            </DialogTitle>
            <DialogDescription>
              Update the core details for this policy. Custom fields are managed separately below.
            </DialogDescription>
          </DialogHeader>

          <form
            id="edit-policy-form"
            onSubmit={handleEditSave}
            noValidate
            className="space-y-4 pt-1"
          >
            {/* Title */}
            <div className="space-y-1.5">
              <Label htmlFor="edit-title" className="text-xs font-medium">
                Title <span className="text-red-500" aria-hidden="true">*</span>
              </Label>
              <Input
                id="edit-title"
                type="text"
                required
                placeholder="e.g. Factory Fire Insurance"
                value={editForm.title ?? ""}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, title: e.target.value }))
                }
                className="h-8 text-sm"
              />
            </div>

            {/* Policy number + status */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="edit-policy-number" className="text-xs font-medium">
                  Policy number
                </Label>
                <Input
                  id="edit-policy-number"
                  type="text"
                  placeholder="e.g. POL-2026-001"
                  value={editForm.policy_number ?? ""}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, policy_number: e.target.value }))
                  }
                  className="h-8 text-sm"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit-status" className="text-xs font-medium">
                  Status
                </Label>
                <Select
                  value={editForm.status ?? ""}
                  onValueChange={(val) =>
                    setEditForm((f) => ({ ...f, status: val }))
                  }
                >
                  <SelectTrigger id="edit-status" className="h-8 text-sm">
                    <SelectValue placeholder="Select status" />
                  </SelectTrigger>
                  <SelectContent>
                    {POLICY_STATUSES.map(({ value, label }) => (
                      <SelectItem key={value} value={value} className="text-sm">
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Sum insured */}
            <div className="space-y-1.5">
              <Label htmlFor="edit-sum-insured" className="text-xs font-medium">
                Sum insured (INR)
              </Label>
              <Input
                id="edit-sum-insured"
                type="text"
                inputMode="decimal"
                placeholder="e.g. 5000000"
                value={editForm.sum_insured_inr ?? ""}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, sum_insured_inr: e.target.value }))
                }
                className="h-8 text-sm"
              />
            </div>

            {/* Premium + GST */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="edit-premium" className="text-xs font-medium">
                  Annual premium (INR)
                </Label>
                <Input
                  id="edit-premium"
                  type="text"
                  inputMode="decimal"
                  placeholder="e.g. 125000"
                  value={editForm.premium_inr ?? ""}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, premium_inr: e.target.value }))
                  }
                  className="h-8 text-sm"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit-gst" className="text-xs font-medium">
                  GST (INR)
                </Label>
                <Input
                  id="edit-gst"
                  type="text"
                  inputMode="decimal"
                  placeholder="e.g. 22500"
                  value={editForm.gst_inr ?? ""}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, gst_inr: e.target.value }))
                  }
                  className="h-8 text-sm"
                />
              </div>
            </div>

            {/* Inception + expiry */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="edit-inception-date" className="text-xs font-medium">
                  Inception date
                </Label>
                <Input
                  id="edit-inception-date"
                  type="date"
                  value={editForm.inception_date ?? ""}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, inception_date: e.target.value }))
                  }
                  className="h-8 text-sm"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit-expiry-date" className="text-xs font-medium">
                  Expiry date
                </Label>
                <Input
                  id="edit-expiry-date"
                  type="date"
                  value={editForm.expiry_date ?? ""}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, expiry_date: e.target.value }))
                  }
                  className="h-8 text-sm"
                />
              </div>
            </div>

            {/* Renewal date */}
            <div className="space-y-1.5">
              <Label htmlFor="edit-renewal-date" className="text-xs font-medium">
                Renewal date{" "}
                <span className="text-zinc-400 font-normal">(optional)</span>
              </Label>
              <Input
                id="edit-renewal-date"
                type="date"
                value={editForm.renewal_date ?? ""}
                onChange={(e) =>
                  setEditForm((f) => ({ ...f, renewal_date: e.target.value }))
                }
                className="h-8 text-sm"
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
              form="edit-policy-form"
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

      {/* Renew Policy dialog */}
      <Dialog open={renewDialogOpen} onOpenChange={setRenewDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <RotateCw className="h-4 w-4 text-brand-600" />
              Renew policy
            </DialogTitle>
            <DialogDescription>
              Enter the details for the new policy term. A linked renewal record will be created and you&apos;ll be taken to it.
            </DialogDescription>
          </DialogHeader>

          <form
            id="renew-policy-form"
            onSubmit={handleRenewPolicy}
            noValidate
            className="space-y-4 pt-1"
          >
            {/* Row: inception + expiry */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="renew-inception-date" className="text-xs font-medium">
                  Inception date
                </Label>
                <Input
                  id="renew-inception-date"
                  type="date"
                  value={renewForm.inception_date ?? ""}
                  onChange={(e) =>
                    setRenewForm((f) => ({ ...f, inception_date: e.target.value }))
                  }
                  className="h-8 text-sm"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="renew-expiry-date" className="text-xs font-medium">
                  Expiry date <span className="text-red-500" aria-hidden="true">*</span>
                </Label>
                <Input
                  id="renew-expiry-date"
                  type="date"
                  required
                  value={renewForm.expiry_date}
                  onChange={(e) => {
                    setRenewExpiryError(null);
                    setRenewForm((f) => ({ ...f, expiry_date: e.target.value }));
                  }}
                  aria-describedby={renewExpiryError ? "renew-expiry-error" : undefined}
                  aria-invalid={!!renewExpiryError}
                  className={cn(
                    "h-8 text-sm",
                    renewExpiryError && "border-red-500 focus-visible:ring-red-500"
                  )}
                />
                {renewExpiryError && (
                  <p id="renew-expiry-error" role="alert" className="text-xs text-red-500">
                    {renewExpiryError}
                  </p>
                )}
              </div>
            </div>

            {/* Renewal date */}
            <div className="space-y-1.5">
              <Label htmlFor="renew-renewal-date" className="text-xs font-medium">
                Renewal date <span className="text-zinc-400 font-normal">(optional)</span>
              </Label>
              <Input
                id="renew-renewal-date"
                type="date"
                value={renewForm.renewal_date ?? ""}
                onChange={(e) =>
                  setRenewForm((f) => ({ ...f, renewal_date: e.target.value }))
                }
                className="h-8 text-sm"
              />
            </div>

            {/* Row: premium + GST */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="renew-premium" className="text-xs font-medium">
                  Annual premium (INR)
                </Label>
                <Input
                  id="renew-premium"
                  type="text"
                  inputMode="decimal"
                  placeholder="e.g. 125000"
                  value={renewForm.premium_inr ?? ""}
                  onChange={(e) =>
                    setRenewForm((f) => ({ ...f, premium_inr: e.target.value }))
                  }
                  className="h-8 text-sm"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="renew-gst" className="text-xs font-medium">
                  GST (INR)
                </Label>
                <Input
                  id="renew-gst"
                  type="text"
                  inputMode="decimal"
                  placeholder="e.g. 22500"
                  value={renewForm.gst_inr ?? ""}
                  onChange={(e) =>
                    setRenewForm((f) => ({ ...f, gst_inr: e.target.value }))
                  }
                  className="h-8 text-sm"
                />
              </div>
            </div>

            {/* Sum insured */}
            <div className="space-y-1.5">
              <Label htmlFor="renew-sum-insured" className="text-xs font-medium">
                Sum insured (INR)
              </Label>
              <Input
                id="renew-sum-insured"
                type="text"
                inputMode="decimal"
                placeholder="e.g. 5000000"
                value={renewForm.sum_insured_inr ?? ""}
                onChange={(e) =>
                  setRenewForm((f) => ({ ...f, sum_insured_inr: e.target.value }))
                }
                className="h-8 text-sm"
              />
            </div>

            {/* Policy number */}
            <div className="space-y-1.5">
              <Label htmlFor="renew-policy-number" className="text-xs font-medium">
                Policy number
              </Label>
              <Input
                id="renew-policy-number"
                type="text"
                placeholder="e.g. POL-2026-001"
                value={renewForm.policy_number ?? ""}
                onChange={(e) =>
                  setRenewForm((f) => ({ ...f, policy_number: e.target.value }))
                }
                className="h-8 text-sm"
              />
            </div>
          </form>

          <DialogFooter className="flex gap-2 sm:justify-end pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setRenewDialogOpen(false)}
              disabled={renewSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form="renew-policy-form"
              size="sm"
              disabled={renewSubmitting}
              className="bg-brand-600 hover:bg-brand-600/90 text-white"
            >
              {renewSubmitting ? (
                <>
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  Creating…
                </>
              ) : (
                <>
                  <RotateCw className="mr-1.5 h-4 w-4" />
                  Renew policy
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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

      {/* Custom Fields */}
      <CustomFieldsCard policy={policy} token={token} onUpdate={setPolicy} />

      {/* Documents */}
      <DocumentsCard policyId={id} token={token} />

      {/* Premium Installments */}
      <InstallmentsCard policyId={id} token={token} />

      {/* Alert Schedule */}
      <AlertRuleCard policyId={id} token={token} />
    </div>
  );
}

// ── Custom Fields card ─────────────────────────────────────────

interface CustomFieldRow {
  key: string;
  value: string;
}

function CustomFieldsCard({
  policy,
  token,
  onUpdate,
}: {
  policy: PolicyRead;
  token: string;
  onUpdate: (updated: PolicyRead) => void;
}) {
  const [rows, setRows] = useState<CustomFieldRow[]>(() =>
    Object.entries(policy.custom_fields ?? {}).map(([key, value]) => ({ key, value }))
  );
  const [saving, setSaving] = useState(false);

  // Re-seed when the policy prop changes (e.g. after edit-policy save)
  useEffect(() => {
    setRows(
      Object.entries(policy.custom_fields ?? {}).map(([key, value]) => ({ key, value }))
    );
  }, [policy]);

  function handleRowChange(
    index: number,
    field: "key" | "value",
    newVal: string
  ) {
    setRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [field]: newVal } : row))
    );
  }

  function handleAddRow() {
    setRows((prev) => [...prev, { key: "", value: "" }]);
  }

  function handleRemoveRow(index: number) {
    setRows((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSave() {
    // Build record: skip empty keys, last-wins on duplicates
    const custom_fields: Record<string, string> = {};
    for (const row of rows) {
      const trimmedKey = row.key.trim();
      if (trimmedKey) {
        custom_fields[trimmedKey] = row.value;
      }
    }
    setSaving(true);
    try {
      const updated = await updatePolicy(token, policy.id, { custom_fields });
      onUpdate(updated);
      toast.success("Custom fields saved.");
    } catch {
      // apiFetch already toasted
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4 pb-3">
        <div>
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-brand-600" />
            Custom Fields
          </CardTitle>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
            Store category-specific details — e.g. Engine No, Chassis No for vehicles; Boiler capacity for machinery.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={handleAddRow}
          aria-label="Add custom field"
        >
          <Plus className="mr-1.5 h-4 w-4" />
          Add field
        </Button>
      </CardHeader>

      <CardContent>
        {rows.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <SlidersHorizontal className="mb-2 h-7 w-7 text-zinc-300" />
            <p className="text-sm text-zinc-500">No custom fields yet — add category-specific details here.</p>
          </div>
        ) : (
          <div className="space-y-3">
            <div
              role="list"
              aria-label="Custom field rows"
              className="space-y-2"
            >
              {rows.map((row, index) => (
                <div
                  key={index}
                  role="listitem"
                  className="flex items-center gap-2"
                >
                  <div className="flex-1 min-w-0">
                    <Label
                      htmlFor={`cf-key-${index}`}
                      className="sr-only"
                    >
                      Field name for row {index + 1}
                    </Label>
                    <Input
                      id={`cf-key-${index}`}
                      type="text"
                      placeholder="Field name"
                      value={row.key}
                      onChange={(e) =>
                        handleRowChange(index, "key", e.target.value)
                      }
                      className="h-8 text-sm"
                      aria-label={`Custom field name, row ${index + 1}`}
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <Label
                      htmlFor={`cf-value-${index}`}
                      className="sr-only"
                    >
                      Field value for row {index + 1}
                    </Label>
                    <Input
                      id={`cf-value-${index}`}
                      type="text"
                      placeholder="Value"
                      value={row.value}
                      onChange={(e) =>
                        handleRowChange(index, "value", e.target.value)
                      }
                      className="h-8 text-sm"
                      aria-label={`Custom field value, row ${index + 1}`}
                    />
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => handleRemoveRow(index)}
                    aria-label={`Remove custom field row ${index + 1}${row.key ? ` (${row.key})` : ""}`}
                    className="h-7 w-7 p-0 shrink-0 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </div>

            <div className="pt-1">
              <Button
                size="sm"
                disabled={saving}
                onClick={handleSave}
                className="bg-brand-600 hover:bg-brand-600/90 text-white"
              >
                {saving ? (
                  <>
                    <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    Saving…
                  </>
                ) : (
                  "Save custom fields"
                )}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Installments card ─────────────────────────────────────────
const TODAY_ISO = new Date().toISOString().slice(0, 10);

function installmentPaymentStatus(
  installments: Installment[]
): "none" | "all_paid" | "partial" | "pending" {
  if (installments.length === 0) return "none";
  const paid = installments.filter((i) => i.status === "paid").length;
  if (paid === installments.length) return "all_paid";
  if (paid > 0) return "partial";
  return "pending";
}

function isOverdue(installment: Installment): boolean {
  return installment.status === "pending" && installment.due_date < TODAY_ISO;
}

function InstallmentsCard({
  policyId,
  token,
}: {
  policyId: string;
  token: string;
}) {
  const [installments, setInstallments] = useState<Installment[]>([]);
  const [loading, setLoading] = useState(true);
  const [payingId, setPayingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Add-installment dialog
  const [addOpen, setAddOpen] = useState(false);
  const [addForm, setAddForm] = useState<InstallmentCreate>({
    amount_inr: "",
    due_date: "",
    note: "",
  });
  const [amountError, setAmountError] = useState<string | null>(null);
  const [dueDateError, setDueDateError] = useState<string | null>(null);
  const [addSubmitting, setAddSubmitting] = useState(false);

  function loadInstallments() {
    setLoading(true);
    getInstallments(token, policyId)
      .then((data) => {
        // Sort ascending by due_date (API may already do this, but ensure it)
        const sorted = [...data].sort((a, b) =>
          a.due_date.localeCompare(b.due_date)
        );
        setInstallments(sorted);
      })
      .catch((err: Error) => {
        toast.error("Failed to load installments.", { description: err.message });
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (token) loadInstallments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [policyId, token]);

  async function handleMarkPaid(installment: Installment) {
    setPayingId(installment.id);
    try {
      await markInstallmentPaid(token, installment.id);
      toast.success(`Installment of ${formatINR(installment.amount_inr)} marked as paid.`);
      loadInstallments();
    } catch {
      // apiFetch already toasted
    } finally {
      setPayingId(null);
    }
  }

  async function handleDelete(installment: Installment) {
    setDeletingId(installment.id);
    try {
      await deleteInstallment(token, installment.id);
      toast.success("Installment deleted.");
      loadInstallments();
    } catch {
      // apiFetch already toasted
    } finally {
      setDeletingId(null);
    }
  }

  function openAddDialog() {
    setAddForm({ amount_inr: "", due_date: "", note: "" });
    setAmountError(null);
    setDueDateError(null);
    setAddOpen(true);
  }

  async function handleAddSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    let hasError = false;

    const trimmedAmount = addForm.amount_inr.trim();
    if (!trimmedAmount || isNaN(Number(trimmedAmount)) || Number(trimmedAmount) <= 0) {
      setAmountError("Enter a valid positive amount.");
      hasError = true;
    } else {
      setAmountError(null);
    }

    if (!addForm.due_date) {
      setDueDateError("Due date is required.");
      hasError = true;
    } else {
      setDueDateError(null);
    }

    if (hasError) return;

    setAddSubmitting(true);
    try {
      const payload: InstallmentCreate = {
        amount_inr: trimmedAmount,
        due_date: addForm.due_date,
        ...(addForm.note?.trim() ? { note: addForm.note.trim() } : {}),
      };
      await addInstallment(token, policyId, payload);
      toast.success("Installment added.");
      setAddOpen(false);
      loadInstallments();
    } catch {
      // apiFetch already toasted
    } finally {
      setAddSubmitting(false);
    }
  }

  // Derived summary figures
  const totalAmount = installments.reduce(
    (sum, i) => sum + Number(i.amount_inr || 0),
    0
  );
  const paidAmount = installments
    .filter((i) => i.status === "paid")
    .reduce((sum, i) => sum + Number(i.amount_inr || 0), 0);
  const paymentStatus = installmentPaymentStatus(installments);

  function PaymentStatusBadge() {
    if (paymentStatus === "none") return null;
    if (paymentStatus === "all_paid")
      return <Badge variant="success">Paid</Badge>;
    if (paymentStatus === "partial")
      return <Badge variant="warning">Partially paid</Badge>;
    return <Badge variant="secondary">Pending</Badge>;
  }

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4 pb-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Wallet className="h-4 w-4 text-brand-600" />
            Premium Installments
          </CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={openAddDialog}
            aria-label="Add installment"
          >
            <Plus className="mr-1.5 h-4 w-4" />
            Add installment
          </Button>
        </CardHeader>

        <CardContent>
          {loading ? (
            <div className="space-y-3">
              <Skeleton className="h-4 w-56" />
              {[1, 2].map((i) => (
                <div key={i} className="flex items-center gap-3">
                  <Skeleton className="h-8 w-8 rounded" />
                  <div className="flex-1 space-y-1">
                    <Skeleton className="h-3 w-32" />
                    <Skeleton className="h-3 w-20" />
                  </div>
                  <Skeleton className="h-7 w-20 rounded" />
                </div>
              ))}
            </div>
          ) : installments.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <IndianRupee className="mb-2 h-7 w-7 text-zinc-300" />
              <p className="text-sm text-zinc-500">No installments tracked.</p>
              <p className="text-xs text-zinc-400 mt-0.5">
                Add one to track premium payments.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Summary line */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                <span className="text-zinc-500 dark:text-zinc-400">
                  Total:{" "}
                  <span className="font-medium text-zinc-900 dark:text-zinc-100">
                    {formatINR(String(totalAmount))}
                  </span>
                </span>
                <span className="text-zinc-500 dark:text-zinc-400">
                  Paid:{" "}
                  <span className="font-medium text-zinc-900 dark:text-zinc-100">
                    {formatINR(String(paidAmount))}
                  </span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">
                    Payment status:
                  </span>
                  <PaymentStatusBadge />
                </span>
              </div>

              {/* Installment rows */}
              <ul
                className="divide-y divide-zinc-100 dark:divide-zinc-800"
                aria-label="Installment list"
              >
                {installments.map((inst) => {
                  const overdue = isOverdue(inst);
                  const isPaying = payingId === inst.id;
                  const isDeleting = deletingId === inst.id;
                  const busy = isPaying || isDeleting;

                  return (
                    <li
                      key={inst.id}
                      className="flex items-start gap-3 py-3"
                    >
                      {/* Amount + status */}
                      <div className="flex-1 min-w-0 space-y-0.5">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-semibold">
                            {formatINR(inst.amount_inr)}
                          </span>
                          {inst.status === "paid" ? (
                            <Badge variant="success" className="text-xs">
                              <CheckCircle className="mr-1 h-3 w-3" />
                              Paid
                            </Badge>
                          ) : overdue ? (
                            <Badge
                              variant="destructive"
                              className="text-xs"
                            >
                              Overdue
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="text-xs">
                              Pending
                            </Badge>
                          )}
                        </div>
                        <p
                          className={cn(
                            "text-xs",
                            overdue
                              ? "text-red-500 dark:text-red-400 font-medium"
                              : "text-zinc-400"
                          )}
                        >
                          Due {formatDate(inst.due_date)}
                          {inst.paid_at && (
                            <> &middot; Paid {formatDate(inst.paid_at)}</>
                          )}
                        </p>
                        {inst.note && (
                          <p className="text-xs text-zinc-400 italic truncate">
                            {inst.note}
                          </p>
                        )}
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1 shrink-0">
                        {inst.status === "pending" && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={busy}
                            onClick={() => handleMarkPaid(inst)}
                            aria-label={`Mark installment of ${formatINR(inst.amount_inr)} as paid`}
                            className="h-7 px-2 text-xs text-brand-600 border-brand-600/40 hover:bg-brand-600/10 dark:text-brand-400 dark:border-brand-600/40 dark:hover:bg-brand-600/10"
                          >
                            {isPaying ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <>
                                <CheckCircle className="mr-1 h-3.5 w-3.5" />
                                Mark paid
                              </>
                            )}
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={busy}
                          onClick={() => handleDelete(inst)}
                          aria-label={`Delete installment of ${formatINR(inst.amount_inr)} due ${formatDate(inst.due_date)}`}
                          className="h-7 w-7 p-0 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
                        >
                          {isDeleting ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add installment dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <IndianRupee className="h-4 w-4 text-brand-600" />
              Add installment
            </DialogTitle>
            <DialogDescription>
              Record a premium installment payment schedule for this policy.
            </DialogDescription>
          </DialogHeader>

          <form
            id="add-installment-form"
            onSubmit={handleAddSubmit}
            noValidate
            className="space-y-4 pt-1"
          >
            {/* Amount */}
            <div className="space-y-1.5">
              <Label htmlFor="inst-amount" className="text-xs font-medium">
                Amount (INR){" "}
                <span className="text-red-500" aria-hidden="true">
                  *
                </span>
              </Label>
              <Input
                id="inst-amount"
                type="number"
                inputMode="decimal"
                min="0.01"
                step="0.01"
                placeholder="e.g. 25000"
                value={addForm.amount_inr}
                onChange={(e) => {
                  setAmountError(null);
                  setAddForm((f) => ({ ...f, amount_inr: e.target.value }));
                }}
                aria-describedby={amountError ? "inst-amount-error" : undefined}
                aria-invalid={!!amountError}
                className={cn(
                  "h-8 text-sm",
                  amountError && "border-red-500 focus-visible:ring-red-500"
                )}
              />
              {amountError && (
                <p id="inst-amount-error" role="alert" className="text-xs text-red-500">
                  {amountError}
                </p>
              )}
            </div>

            {/* Due date */}
            <div className="space-y-1.5">
              <Label htmlFor="inst-due-date" className="text-xs font-medium">
                Due date{" "}
                <span className="text-red-500" aria-hidden="true">
                  *
                </span>
              </Label>
              <Input
                id="inst-due-date"
                type="date"
                required
                value={addForm.due_date}
                onChange={(e) => {
                  setDueDateError(null);
                  setAddForm((f) => ({ ...f, due_date: e.target.value }));
                }}
                aria-describedby={dueDateError ? "inst-due-date-error" : undefined}
                aria-invalid={!!dueDateError}
                className={cn(
                  "h-8 text-sm",
                  dueDateError && "border-red-500 focus-visible:ring-red-500"
                )}
              />
              {dueDateError && (
                <p id="inst-due-date-error" role="alert" className="text-xs text-red-500">
                  {dueDateError}
                </p>
              )}
            </div>

            {/* Note */}
            <div className="space-y-1.5">
              <Label htmlFor="inst-note" className="text-xs font-medium">
                Note{" "}
                <span className="text-zinc-400 font-normal">(optional)</span>
              </Label>
              <Input
                id="inst-note"
                type="text"
                placeholder="e.g. Q1 installment"
                value={addForm.note ?? ""}
                onChange={(e) =>
                  setAddForm((f) => ({ ...f, note: e.target.value }))
                }
                className="h-8 text-sm"
              />
            </div>
          </form>

          <DialogFooter className="flex gap-2 sm:justify-end pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setAddOpen(false)}
              disabled={addSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form="add-installment-form"
              size="sm"
              disabled={addSubmitting}
              className="bg-brand-600 hover:bg-brand-600/90 text-white"
            >
              {addSubmitting ? (
                <>
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                <>
                  <Plus className="mr-1.5 h-4 w-4" />
                  Add
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ── Alert Rule card ───────────────────────────────────────────
const STANDARD_LEAD_DAYS = [60, 30, 15, 7, 1];

type IconComponent = React.ComponentType<{ className?: string }>;

const CHANNEL_OPTIONS: { value: AlertChannel; label: string; Icon: IconComponent }[] = [
  { value: "whatsapp", label: "WhatsApp", Icon: MessageSquare },
  { value: "email", label: "Email", Icon: Mail },
  { value: "sms", label: "SMS", Icon: Phone },
  { value: "telegram", label: "Telegram", Icon: Send },
];

function AlertRuleCard({
  policyId,
  token,
}: {
  policyId: string;
  token: string;
}) {
  const [ruleLoading, setRuleLoading] = useState(true);
  const [isActive, setIsActive] = useState(true);
  const [leadDays, setLeadDays] = useState<number[]>([60, 30, 15, 7, 1]);
  const [channels, setChannels] = useState<AlertChannel[]>(["email"]);
  const [escalate, setEscalate] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!token) return;
    setRuleLoading(true);
    getAlertRule(token, policyId)
      .then((rule: AlertRuleRead) => {
        setIsActive(rule.is_active);
        setLeadDays(rule.lead_days.length > 0 ? rule.lead_days : [60, 30, 15, 7, 1]);
        setChannels(
          rule.channels.length > 0
            ? (rule.channels as AlertChannel[])
            : ["email"]
        );
        setEscalate(rule.escalate);
      })
      .catch((err: Error) => {
        toast.error("Failed to load alert schedule.", {
          description: err.message,
        });
      })
      .finally(() => setRuleLoading(false));
  }, [policyId, token]);

  function toggleLeadDay(day: number) {
    setLeadDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
    );
  }

  function toggleChannel(ch: AlertChannel) {
    setChannels((prev) =>
      prev.includes(ch) ? prev.filter((c) => c !== ch) : [...prev, ch]
    );
  }

  async function handleSave() {
    setSaving(true);
    try {
      await setAlertRule(token, policyId, {
        is_active: isActive,
        lead_days: leadDays,
        channels,
        escalate,
      });
      toast.success("Alert schedule saved.");
    } catch {
      // apiFetch already toasted
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Bell className="h-4 w-4 text-brand-600" />
          Alert Schedule
        </CardTitle>
      </CardHeader>
      <CardContent>
        {ruleLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-5 w-48" />
          </div>
        ) : (
          <div className="space-y-5">
            {/* is_active toggle */}
            <div className="flex items-center justify-between gap-4">
              <Label
                htmlFor="alertRuleActive"
                className="text-sm font-medium cursor-pointer"
              >
                Alerts enabled
              </Label>
              <Switch
                id="alertRuleActive"
                checked={isActive}
                onCheckedChange={setIsActive}
              />
            </div>

            {/* Lead days */}
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                Remind me before expiry
              </p>
              <div className="flex flex-wrap gap-2" role="group" aria-label="Lead days selection">
                {STANDARD_LEAD_DAYS.map((day) => {
                  const selected = leadDays.includes(day);
                  return (
                    <button
                      key={day}
                      type="button"
                      onClick={() => toggleLeadDay(day)}
                      aria-pressed={selected}
                      className={cn(
                        "rounded-full px-3 py-1 text-xs font-semibold border transition-colors",
                        "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600",
                        selected
                          ? "bg-brand-600 text-white border-brand-600"
                          : "bg-transparent text-zinc-600 border-zinc-300 hover:border-brand-600 hover:text-brand-600 dark:text-zinc-400 dark:border-zinc-700 dark:hover:border-brand-600 dark:hover:text-brand-600"
                      )}
                    >
                      {day}d
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Channels */}
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                Channels
              </p>
              <div className="flex flex-wrap gap-2" role="group" aria-label="Channel selection">
                {CHANNEL_OPTIONS.map(({ value, label, Icon }) => {
                  const selected = channels.includes(value);
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => toggleChannel(value)}
                      aria-pressed={selected}
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold border transition-colors",
                        "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600",
                        selected
                          ? "bg-brand-600 text-white border-brand-600"
                          : "bg-transparent text-zinc-600 border-zinc-300 hover:border-brand-600 hover:text-brand-600 dark:text-zinc-400 dark:border-zinc-700 dark:hover:border-brand-600 dark:hover:text-brand-600"
                      )}
                    >
                      <Icon className="h-3.5 w-3.5 shrink-0" />
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Escalate toggle */}
            <div className="flex items-center justify-between gap-4">
              <Label
                htmlFor="alertRuleEscalate"
                className="text-sm font-medium cursor-pointer"
              >
                Escalate if unacknowledged
              </Label>
              <Switch
                id="alertRuleEscalate"
                checked={escalate}
                onCheckedChange={setEscalate}
              />
            </div>

            {/* Save */}
            <div className="pt-1">
              <Button
                size="sm"
                disabled={saving}
                onClick={handleSave}
                className="bg-brand-600 hover:bg-brand-600/90 text-white"
              >
                {saving ? (
                  <>
                    <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    Saving…
                  </>
                ) : (
                  "Save"
                )}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Documents card

function DocumentsCard({
  policyId,
  token,
}: {
  policyId: string;
  token: string;
}) {
  const [docs, setDocs] = useState<DocumentRead[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [indexingId, setIndexingId] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function loadDocs() {
    setDocsLoading(true);
    listDocuments(token, policyId)
      .then(setDocs)
      .catch((err: Error) => {
        toast.error("Failed to load documents", { description: err.message });
      })
      .finally(() => setDocsLoading(false));
  }

  useEffect(() => {
    if (token) loadDocs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [policyId, token]);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    // Reset the input so the same file can be re-selected after an error.
    e.target.value = "";

    // Client-side validation
    if (!ALLOWED_TYPES.includes(file.type)) {
      toast.error("Unsupported file type.", {
        description: "Please upload a PDF, PNG, JPG, or WebP.",
      });
      return;
    }
    if (file.size > MAX_BYTES) {
      toast.error("File too large.", {
        description: "Maximum file size is 20 MB.",
      });
      return;
    }

    setUploading(true);
    try {
      // Step 1 — get a signed PUT URL from the backend.
      const { upload_url, storage_path } = await getDocumentUploadUrl(
        token,
        policyId,
        { file_name: file.name, content_type: file.type }
      );

      // Step 2 — PUT the raw bytes directly to Supabase Storage.
      await uploadFileToStorage(upload_url, file);

      // Step 3 — record the document in the DB so the backend creates the row.
      await recordDocument(token, policyId, {
        storage_path,
        file_name: file.name,
        content_type: file.type,
        size_bytes: file.size,
        doc_type: "policy",
      });

      toast.success(`"${file.name}" uploaded.`);
      loadDocs();
    } catch (err: unknown) {
      // apiFetch already shows a toast for backend errors; only catch storage errors here.
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.startsWith("Storage upload failed")) {
        toast.error("Upload failed.", { description: msg });
      }
      // Otherwise apiFetch already toasted.
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(doc: DocumentRead) {
    setDeletingId(doc.id);
    try {
      await deleteDocument(token, doc.id);
      toast.success(`"${doc.file_name}" deleted.`);
      loadDocs();
    } catch {
      // apiFetch already showed a toast.
    } finally {
      setDeletingId(null);
    }
  }

  async function handleIndex(doc: DocumentRead) {
    setIndexingId(doc.id);
    try {
      const res = await ingestDocument(token, policyId, doc.id);
      if (res.chunks === 0) {
        toast.info("No extractable text found.", {
          description: `"${doc.file_name}" may not be a text-based PDF.`,
        });
      } else {
        toast.success(`Indexed ${res.chunks} chunks for AI search.`, {
          description: `"${doc.file_name}" is now searchable via Ask sVault.`,
        });
      }
    } catch {
      // apiFetch already showed a toast (including 402 entitlement_required).
    } finally {
      setIndexingId(null);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4 pb-3">
        <CardTitle className="text-sm font-semibold">Documents</CardTitle>
        <div>
          {/* Hidden file input */}
          <input
            ref={fileRef}
            type="file"
            accept={ALLOWED_EXTS}
            className="sr-only"
            aria-label="Upload policy document"
            onChange={handleFileChange}
            disabled={uploading}
          />
          <Button
            size="sm"
            variant="outline"
            disabled={uploading}
            onClick={() => fileRef.current?.click()}
          >
            {uploading ? (
              <>
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                Uploading…
              </>
            ) : (
              <>
                <Upload className="mr-1.5 h-4 w-4" />
                Upload
              </>
            )}
          </Button>
        </div>
      </CardHeader>

      <CardContent>
        {docsLoading ? (
          <div className="space-y-2">
            {[1, 2].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-8 w-8 rounded" />
                <div className="flex-1 space-y-1">
                  <Skeleton className="h-3 w-48" />
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
            ))}
          </div>
        ) : docs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <Paperclip className="mb-2 h-7 w-7 text-zinc-300" />
            <p className="text-sm text-zinc-500">No documents attached.</p>
            <p className="text-xs text-zinc-400 mt-0.5">
              Upload a PDF or image (max 20 MB).
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {docs.map((doc) => (
              <li key={doc.id} className="flex items-center gap-3 py-2.5">
                <FileText className="h-5 w-5 shrink-0 text-zinc-400" />
                <div className="flex-1 min-w-0">
                  <p
                    className="truncate text-sm font-medium"
                    title={doc.file_name}
                  >
                    {doc.file_name}
                  </p>
                  <p className="text-xs text-zinc-400">
                    {formatBytes(doc.size_bytes)} &middot; v{doc.version} &middot;{" "}
                    {formatDate(doc.created_at)}
                  </p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`Index ${doc.file_name} for AI search`}
                    title="Index for AI"
                    disabled={indexingId === doc.id}
                    onClick={() => handleIndex(doc)}
                    className="text-zinc-500 hover:text-brand-600 hover:bg-brand-600/10 dark:hover:bg-brand-600/10"
                  >
                    {indexingId === doc.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Sparkles className="h-4 w-4" />
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    asChild
                    aria-label={`Download ${doc.file_name}`}
                  >
                    <a
                      href={doc.download_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Download className="h-4 w-4" />
                    </a>
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`Delete ${doc.file_name}`}
                    disabled={deletingId === doc.id}
                    onClick={() => handleDelete(doc)}
                    className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
                  >
                    {deletingId === doc.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

// Skeleton / Error helpers

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
