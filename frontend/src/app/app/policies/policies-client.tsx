"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  getPolicies,
  getOrgs,
  createPolicy,
  setAlertRule,
  type PolicyRead,
  type OrgRead,
  type PolicyCategory,
  type PolicyExtraction,
} from "@/lib/api";
import {
  formatDate,
  formatINR,
  daysLeftVariant,
  categorylabel,
  statusLabel,
  cn,
} from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
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
import { Plus, Search, FileText, AlertTriangle, Sparkles } from "lucide-react";
import AiIntakeDialog from "./ai-intake-dialog";

const CATEGORIES: { value: PolicyCategory; label: string }[] = [
  { value: "vehicle", label: "Vehicle" },
  { value: "machinery", label: "Machinery" },
  { value: "plant", label: "Plant" },
  { value: "factory_property", label: "Factory / Property" },
  { value: "employees_group_health", label: "Employees (GHI)" },
  { value: "key_person", label: "Key Person" },
  { value: "stock_raw_material", label: "Stock – Raw Material" },
  { value: "stock_finished_goods", label: "Stock – Finished Goods" },
  { value: "other", label: "Other" },
];

const STATUSES = [
  "draft",
  "pending_approval",
  "active",
  "expiring",
  "lapsed",
  "renewed",
  "cancelled",
];

interface Props {
  token: string;
}

export default function PoliciesClient({ token }: Props) {
  const router = useRouter();
  const [policies, setPolicies] = useState<PolicyRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [filterCategory, setFilterCategory] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [search, setSearch] = useState("");

  // Add policy dialog
  const [dialogOpen, setDialogOpen] = useState(false);
  const [orgs, setOrgs] = useState<OrgRead[]>([]);
  const [orgsLoading, setOrgsLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // New policy form
  const [newTitle, setNewTitle] = useState("");
  const [newCategory, setNewCategory] = useState<PolicyCategory>("vehicle");
  const [newOrgId, setNewOrgId] = useState("");
  const [newPolicyNumber, setNewPolicyNumber] = useState("");
  const [newSumInsured, setNewSumInsured] = useState("");
  const [newPremium, setNewPremium] = useState("");
  const [newGst, setNewGst] = useState("");
  const [newInceptionDate, setNewInceptionDate] = useState("");
  const [newExpiryDate, setNewExpiryDate] = useState("");

  // AI pre-fill state
  const [aiPrefilled, setAiPrefilled] = useState(false);

  // Renewal alerts checkbox (shown in the create form)
  const [enableAlerts, setEnableAlerts] = useState(true);

  // AI Intake dialog
  const [intakeOpen, setIntakeOpen] = useState(false);

  const fetchPolicies = useCallback(() => {
    if (!token) return;
    setLoading(true);
    getPolicies(token, {
      category: filterCategory || undefined,
      status: filterStatus || undefined,
      limit: 50,
    })
      .then((res) => {
        setPolicies(Array.isArray(res) ? res : []);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token, filterCategory, filterStatus]);

  useEffect(() => {
    fetchPolicies();
  }, [fetchPolicies]);

  // Load orgs when dialog opens
  useEffect(() => {
    if (!dialogOpen || orgs.length > 0) return;
    setOrgsLoading(true);
    getOrgs(token)
      .then((list) => {
        setOrgs(list);
        if (list.length > 0) setNewOrgId(list[0].id);
      })
      .catch(() => toast.error("Could not load organizations."))
      .finally(() => setOrgsLoading(false));
  }, [dialogOpen, orgs.length, token]);

  // AI Intake: populate the create-policy form from an extraction result
  function handleExtracted(extraction: PolicyExtraction) {
    setNewCategory(extraction.category ?? "other");
    setNewTitle(extraction.title ?? "");
    setNewPolicyNumber(extraction.policy_number ?? "");
    setNewSumInsured(extraction.sum_insured_inr ?? "");
    setNewPremium(extraction.premium_inr ?? "");
    setNewGst(extraction.gst_inr ?? "");
    setNewInceptionDate(extraction.inception_date ?? "");
    setNewExpiryDate(extraction.expiry_date ?? "");
    setAiPrefilled(true);
    // Open the create dialog in pre-filled (review) mode
    setDialogOpen(true);
    // Surface insurer name hint — no provider_id field on the form
    if (extraction.insurer_name) {
      toast.info(`Insurer: ${extraction.insurer_name}`, {
        description: "Add them under Providers to link future policies.",
        duration: 8000,
      });
    }
  }

  async function handleAddPolicy(e: React.FormEvent) {
    e.preventDefault();
    if (!newOrgId || !newTitle) return;
    setSubmitting(true);
    try {
      const created = await createPolicy(token, {
        org_id: newOrgId,
        category: newCategory,
        title: newTitle,
        policy_number: newPolicyNumber || undefined,
        sum_insured_inr: newSumInsured || undefined,
        premium_inr: newPremium || undefined,
        gst_inr: newGst || undefined,
        inception_date: newInceptionDate || undefined,
        expiry_date: newExpiryDate || undefined,
      });
      toast.success("Policy created.");
      // Best-effort renewal alerts — never block the success path
      if (enableAlerts) {
        setAlertRule(token, created.id, {
          lead_days: [60, 30, 15, 7, 1],
          channels: ["email"],
          escalate: false,
          is_active: true,
        }).catch(() => {
          toast.warning("Policy saved, but alerts could not be set up.", {
            description: "Visit the policy page to configure them manually.",
          });
        });
      }
      setDialogOpen(false);
      resetForm();
      fetchPolicies();
    } catch {
      // Error toast handled by API client
    } finally {
      setSubmitting(false);
    }
  }

  function resetForm() {
    setNewTitle("");
    setNewCategory("vehicle");
    setNewPolicyNumber("");
    setNewSumInsured("");
    setNewPremium("");
    setNewGst("");
    setNewInceptionDate("");
    setNewExpiryDate("");
    setAiPrefilled(false);
    setEnableAlerts(true);
  }

  // Client-side search filter
  const displayed = policies.filter((p) =>
    search
      ? p.title.toLowerCase().includes(search.toLowerCase()) ||
        (p.policy_number?.toLowerCase().includes(search.toLowerCase()) ?? false)
      : true
  );

  const statusVariant = (s: string): "success" | "warning" | "destructive" | "secondary" => {
    if (s === "active") return "success";
    if (s === "expiring") return "warning";
    if (s === "lapsed" || s === "cancelled") return "destructive";
    return "secondary";
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Policies</h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Manage your insurance portfolio
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 shrink-0">
          {/* AI Intake button */}
          <Button
            size="sm"
            variant="outline"
            onClick={() => setIntakeOpen(true)}
            aria-label="AI Policy Intake — extract fields from a PDF"
          >
            <Sparkles className="mr-1.5 h-4 w-4 text-brand-600" aria-hidden="true" />
            AI Intake
          </Button>

          {/* AI Intake dialog (standalone, no DialogTrigger needed) */}
          <AiIntakeDialog
            open={intakeOpen}
            onOpenChange={setIntakeOpen}
            token={token}
            onExtracted={handleExtracted}
            onEnterManually={() => {
              resetForm();
              setDialogOpen(true);
            }}
          />

          {/* Manual "Add Policy" dialog */}
          <Dialog
            open={dialogOpen}
            onOpenChange={(v) => {
              setDialogOpen(v);
              if (!v) resetForm();
            }}
          >
            <DialogTrigger asChild>
              <Button size="sm" className="shrink-0">
                <Plus className="mr-1.5 h-4 w-4" />
                Add Policy
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {aiPrefilled ? (
                    <>
                      Review Policy
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                          "bg-brand-600/10 text-brand-600 dark:bg-brand-600/20 dark:text-brand-400"
                        )}
                        aria-label="Fields pre-filled by AI — please review"
                      >
                        <Sparkles className="h-3 w-3" aria-hidden="true" />
                        AI-filled — please review
                      </span>
                    </>
                  ) : (
                    "Add Policy"
                  )}
                </DialogTitle>
              </DialogHeader>
              <form onSubmit={handleAddPolicy} className="space-y-4 py-2">
                <div className="space-y-1.5">
                  <Label htmlFor="newTitle">Title *</Label>
                  <Input
                    id="newTitle"
                    placeholder="Motor fleet insurance 2025"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    required
                    disabled={submitting}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="newCategory">Category *</Label>
                    <Select
                      value={newCategory}
                      onValueChange={(v) => setNewCategory(v as PolicyCategory)}
                      disabled={submitting}
                    >
                      <SelectTrigger id="newCategory">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {CATEGORIES.map((c) => (
                          <SelectItem key={c.value} value={c.value}>
                            {c.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="newOrg">Organization *</Label>
                    {orgsLoading ? (
                      <Skeleton className="h-9 w-full" />
                    ) : (
                      <Select
                        value={newOrgId}
                        onValueChange={setNewOrgId}
                        disabled={submitting || orgs.length === 0}
                      >
                        <SelectTrigger id="newOrg">
                          <SelectValue placeholder="Select org" />
                        </SelectTrigger>
                        <SelectContent>
                          {orgs.map((o) => (
                            <SelectItem key={o.id} value={o.id}>
                              {o.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="newPolicyNumber">Policy Number</Label>
                  <Input
                    id="newPolicyNumber"
                    placeholder="POL-2025-00123"
                    value={newPolicyNumber}
                    onChange={(e) => setNewPolicyNumber(e.target.value)}
                    disabled={submitting}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="newSumInsured">Sum Insured (₹)</Label>
                    <Input
                      id="newSumInsured"
                      type="number"
                      placeholder="5000000"
                      value={newSumInsured}
                      onChange={(e) => setNewSumInsured(e.target.value)}
                      disabled={submitting}
                      min="0"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="newPremium">Premium (₹)</Label>
                    <Input
                      id="newPremium"
                      type="number"
                      placeholder="75000"
                      value={newPremium}
                      onChange={(e) => setNewPremium(e.target.value)}
                      disabled={submitting}
                      min="0"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="newGst">GST (₹)</Label>
                  <Input
                    id="newGst"
                    type="number"
                    placeholder="13500"
                    value={newGst}
                    onChange={(e) => setNewGst(e.target.value)}
                    disabled={submitting}
                    min="0"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="newInceptionDate">Inception Date</Label>
                    <Input
                      id="newInceptionDate"
                      type="date"
                      value={newInceptionDate}
                      onChange={(e) => setNewInceptionDate(e.target.value)}
                      disabled={submitting}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="newExpiryDate">Expiry Date</Label>
                    <Input
                      id="newExpiryDate"
                      type="date"
                      value={newExpiryDate}
                      onChange={(e) => setNewExpiryDate(e.target.value)}
                      disabled={submitting}
                    />
                  </div>
                </div>

                {/* Renewal alerts opt-in */}
                <div
                  className={cn(
                    "flex items-start gap-3 rounded-lg border p-3",
                    "border-zinc-200 dark:border-zinc-700"
                  )}
                >
                  <Checkbox
                    id="enableAlerts"
                    checked={enableAlerts}
                    onCheckedChange={(v) => setEnableAlerts(Boolean(v))}
                    disabled={submitting}
                    className="mt-0.5"
                  />
                  <div className="space-y-0.5">
                    <Label
                      htmlFor="enableAlerts"
                      className="cursor-pointer text-sm font-medium leading-tight"
                    >
                      Set up renewal alerts
                    </Label>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      Email reminders at 60, 30, 15, 7, and 1 day before expiry.
                    </p>
                  </div>
                </div>

                <DialogFooter>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setDialogOpen(false);
                      resetForm();
                    }}
                    disabled={submitting}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={submitting || !newTitle || !newOrgId}>
                    {submitting ? "Saving…" : aiPrefilled ? "Create Policy" : "Add Policy"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
          <Input
            placeholder="Search policies…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select
          value={filterCategory || "all"}
          onValueChange={(v) => setFilterCategory(v === "all" ? "" : v)}
        >
          <SelectTrigger className="w-44">
            <SelectValue placeholder="All categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            {CATEGORIES.map((c) => (
              <SelectItem key={c.value} value={c.value}>
                {c.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={filterStatus || "all"}
          onValueChange={(v) => setFilterStatus(v === "all" ? "" : v)}
        >
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {statusLabel(s)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      {loading ? (
        <TableSkeleton />
      ) : error ? (
        <ErrorState message={error} />
      ) : displayed.length === 0 ? (
        <EmptyState hasFilters={!!(filterCategory || filterStatus || search)} />
      ) : (
        <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Expiry</TableHead>
                <TableHead className="text-right">Sum Insured</TableHead>
                <TableHead className="text-right">Premium</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {displayed.map((policy) => {
                const daysLeft = policy.expiry_date
                  ? Math.ceil(
                      (new Date(policy.expiry_date).getTime() - Date.now()) /
                        86400000
                    )
                  : null;
                return (
                  <TableRow
                    key={policy.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/app/policies/${policy.id}`)}
                  >
                    <TableCell>
                      <div className="font-medium">{policy.title}</div>
                      {policy.policy_number && (
                        <div className="text-xs text-zinc-400">
                          {policy.policy_number}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-zinc-500">
                      {categorylabel(policy.category)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(policy.status)}>
                        {statusLabel(policy.status)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="text-zinc-500">
                        {formatDate(policy.expiry_date)}
                      </div>
                      {daysLeft != null && (
                        <Badge
                          variant={daysLeftVariant(daysLeft)}
                          className={cn("mt-1 text-xs", daysLeft < 0 ? "" : "")}
                        >
                          {daysLeft < 0
                            ? `Expired ${Math.abs(daysLeft)}d ago`
                            : `${daysLeft}d left`}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatINR(policy.sum_insured_inr)}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatINR(policy.premium_inr)}
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
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}

function EmptyState({ hasFilters }: { hasFilters: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <FileText className="mb-3 h-10 w-10 text-zinc-300" />
      <h3 className="font-semibold">
        {hasFilters ? "No matching policies" : "No policies yet"}
      </h3>
      <p className="mt-1 text-sm text-zinc-400">
        {hasFilters
          ? "Try clearing the filters."
          : "Click \"Add Policy\" to get started."}
      </p>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <AlertTriangle className="mb-3 h-10 w-10 text-red-400" />
      <h3 className="font-semibold">Failed to load policies</h3>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
    </div>
  );
}
