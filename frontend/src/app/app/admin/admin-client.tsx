"use client";

import { useEffect, useState, useCallback } from "react";
import {
  adminGetAnalytics,
  adminListPlans,
  adminCreatePlan,
  adminUpdatePlan,
  adminListTenants,
  adminSuspendTenant,
  adminActivateTenant,
  adminGetSetting,
  adminSetSetting,
  type PlatformAnalytics,
  type PlanRead,
  type PlanWrite,
  type PlatformTenant,
  type PlatformSetting,
} from "@/lib/api";
import { formatINR, formatDate, cn } from "@/lib/utils";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
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
  ShieldCheck,
  Users,
  TrendingUp,
  AlertTriangle,
  Loader2,
  Plus,
  Pencil,
  Eye,
  EyeOff,
  CheckCircle2,
  CircleDashed,
  BarChart3,
  Key,
} from "lucide-react";

// ── Constants ───────────────────────────────────────────────────────────
const TIER_OPTIONS = ["free", "starter", "professional", "enterprise"] as const;
type Tier = (typeof TIER_OPTIONS)[number];

interface SecretKeyDef {
  key: string;
  label: string;
  description: string;
}

const SECRET_KEYS: SecretKeyDef[] = [
  {
    key: "svault_ai_api_key",
    label: "AI (Claude) API Key",
    description: "Anthropic API key for Ask sVault / RAG features.",
  },
  {
    key: "razorpay_key_id",
    label: "Razorpay Key ID",
    description: "Public Razorpay key identifier.",
  },
  {
    key: "razorpay_key_secret",
    label: "Razorpay Key Secret",
    description: "Razorpay secret key for server-side requests.",
  },
  {
    key: "razorpay_webhook_secret",
    label: "Razorpay Webhook Secret",
    description: "Signature secret for verifying Razorpay webhook payloads.",
  },
  {
    key: "whatsapp_token",
    label: "WhatsApp Token",
    description: "WhatsApp Business API bearer token.",
  },
  {
    key: "sms_api_key",
    label: "SMS API Key",
    description: "DLT-registered SMS gateway API key.",
  },
  {
    key: "telegram_bot_token",
    label: "Telegram Bot Token",
    description: "Telegram Bot API token for push notifications.",
  },
  {
    key: "email_api_key",
    label: "Email API Key",
    description: "Transactional email provider API key.",
  },
];

// ── Props ───────────────────────────────────────────────────────────
interface Props {
  token: string;
}

// ── Root component ───────────────────────────────────────────────
export default function AdminClient({ token }: Props) {
  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Page header */}
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white">
          <ShieldCheck className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Platform Admin</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">
            Manage plans, tenants, secrets, and platform analytics.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="w-full sm:w-auto">
          <TabsTrigger value="overview" className="gap-1.5">
            <BarChart3 className="h-3.5 w-3.5" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="plans" className="gap-1.5">
            <TrendingUp className="h-3.5 w-3.5" />
            Plans
          </TabsTrigger>
          <TabsTrigger value="tenants" className="gap-1.5">
            <Users className="h-3.5 w-3.5" />
            Tenants
          </TabsTrigger>
          <TabsTrigger value="settings" className="gap-1.5">
            <Key className="h-3.5 w-3.5" />
            Settings
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <OverviewTab token={token} />
        </TabsContent>
        <TabsContent value="plans">
          <PlansTab token={token} />
        </TabsContent>
        <TabsContent value="tenants">
          <TenantsTab token={token} />
        </TabsContent>
        <TabsContent value="settings">
          <SettingsTab token={token} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ── Overview Tab ───────────────────────────────────────────────
function OverviewTab({ token }: { token: string }) {
  const [analytics, setAnalytics] = useState<PlatformAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    adminGetAnalytics(token)
      .then(setAnalytics)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <OverviewSkeleton />;
  if (error) return <TabError message={error} onRetry={() => window.location.reload()} />;
  if (!analytics) return null;

  const { tenants, subscriptions, by_tier, mrr_inr } = analytics;

  const metricCards = [
    {
      label: "Total Tenants",
      value: String(tenants.total),
      icon: Users,
      color: "text-brand-600",
    },
    {
      label: "Active Tenants",
      value: String(tenants.active),
      icon: CheckCircle2,
      color: "text-emerald-600",
    },
    {
      label: "Suspended",
      value: String(tenants.suspended),
      icon: AlertTriangle,
      color: "text-red-500",
    },
    {
      label: "Monthly Revenue",
      value: formatINR(mrr_inr),
      icon: TrendingUp,
      color: "text-brand-600",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Metric cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {metricCards.map(({ label, value, icon: Icon, color }) => (
          <Card key={label}>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <p className="text-sm text-zinc-500 dark:text-zinc-400">{label}</p>
                <Icon className={cn("h-4 w-4 shrink-0", color)} />
              </div>
              <p className="mt-1.5 text-3xl font-bold tracking-tight">{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Sub-lists row */}
      <div className="grid gap-4 sm:grid-cols-2">
        {/* Subscriptions by status */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold">Subscriptions by Status</CardTitle>
          </CardHeader>
          <CardContent>
            {Object.keys(subscriptions).length === 0 ? (
              <p className="text-sm text-zinc-400">No subscription data.</p>
            ) : (
              <ul className="space-y-2">
                {Object.entries(subscriptions).map(([status, count]) => (
                  <li
                    key={status}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="capitalize text-zinc-600 dark:text-zinc-400">
                      {status.replace(/_/g, " ")}
                    </span>
                    <Badge variant={subStatusVariant(status)} className="tabular-nums">
                      {count}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Active by tier */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold">Active Tenants by Tier</CardTitle>
          </CardHeader>
          <CardContent>
            {by_tier.length === 0 ? (
              <p className="text-sm text-zinc-400">No tier data.</p>
            ) : (
              <ul className="space-y-2">
                {by_tier.map(({ tier, count }) => (
                  <li
                    key={tier}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="capitalize text-zinc-600 dark:text-zinc-400">
                      {tier}
                    </span>
                    <span className="font-semibold tabular-nums">{count}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function subStatusVariant(
  status: string
): "success" | "warning" | "destructive" | "secondary" {
  if (status === "active") return "success";
  if (status === "trialing") return "warning";
  if (status === "past_due" || status === "cancelled" || status === "expired")
    return "destructive";
  return "secondary";
}

// ── Plans Tab ────────────────────────────────────────────────────────
function PlansTab({ token }: { token: string }) {
  const [plans, setPlans] = useState<PlanRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPlans = useCallback(() => {
    setLoading(true);
    adminListPlans(token)
      .then(setPlans)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    fetchPlans();
  }, [fetchPlans]);

  if (loading) return <TableSkeleton rows={4} cols={5} />;
  if (error) return <TabError message={error} onRetry={fetchPlans} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          {plans.length} plan{plans.length !== 1 ? "s" : ""} total (including inactive).
        </p>
        <NewPlanDialog token={token} onCreated={fetchPlans} />
      </div>

      {plans.length === 0 ? (
        <EmptyState icon={TrendingUp} message="No plans defined yet." />
      ) : (
        <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tier</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Period</TableHead>
                <TableHead>Active</TableHead>
                <TableHead>Razorpay Plan ID</TableHead>
                <TableHead className="text-right">Edit</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {plans.map((plan) => (
                <TableRow key={plan.id}>
                  <TableCell>
                    <Badge variant="secondary" className="capitalize">
                      {plan.tier}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-medium">{plan.name}</TableCell>
                  <TableCell className="tabular-nums">{formatINR(plan.price_inr)}</TableCell>
                  <TableCell className="capitalize text-zinc-500">{plan.billing_period}</TableCell>
                  <TableCell>
                    <Badge variant={plan.is_active ? "success" : "secondary"}>
                      {plan.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {plan.razorpay_plan_id ? (
                      <span className="font-mono text-xs text-zinc-600 dark:text-zinc-400">
                        {plan.razorpay_plan_id}
                      </span>
                    ) : (
                      <span className="text-zinc-400">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <EditPlanDialog token={token} plan={plan} onSaved={fetchPlans} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

// ── Edit Plan Dialog ───────────────────────────────────────────────
function EditPlanDialog({
  token,
  plan,
  onSaved,
}: {
  token: string;
  plan: PlanRead;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  // Form state
  const [name, setName] = useState(plan.name);
  const [description, setDescription] = useState(plan.description ?? "");
  const [priceInr, setPriceInr] = useState(plan.price_inr);
  const [billingPeriod, setBillingPeriod] = useState(plan.billing_period);
  const [isActive, setIsActive] = useState(plan.is_active);
  const [razorpayPlanId, setRazorpayPlanId] = useState(plan.razorpay_plan_id ?? "");
  const [entitlementsJson, setEntitlementsJson] = useState(
    JSON.stringify(plan.entitlements, null, 2)
  );

  function resetForm() {
    setName(plan.name);
    setDescription(plan.description ?? "");
    setPriceInr(plan.price_inr);
    setBillingPeriod(plan.billing_period);
    setIsActive(plan.is_active);
    setRazorpayPlanId(plan.razorpay_plan_id ?? "");
    setEntitlementsJson(JSON.stringify(plan.entitlements, null, 2));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();

    let parsedEntitlements: Record<string, unknown>;
    try {
      parsedEntitlements = JSON.parse(entitlementsJson) as Record<string, unknown>;
    } catch {
      toast.error("Invalid JSON in Entitlements field. Please fix and try again.");
      return;
    }

    setSaving(true);
    try {
      const body: PlanWrite = {
        name: name.trim(),
        description: description.trim() || null,
        price_inr: priceInr,
        billing_period: billingPeriod,
        is_active: isActive,
        razorpay_plan_id: razorpayPlanId.trim() || null,
        entitlements: parsedEntitlements,
      };
      await adminUpdatePlan(token, plan.id, body);
      toast.success("Plan updated.");
      setOpen(false);
      onSaved();
    } catch {
      // apiFetch already toasted
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (v) resetForm();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" className="h-7 px-2.5 text-xs">
          <Pencil className="mr-1 h-3 w-3" />
          Edit
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit Plan — {plan.name}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSave} className="space-y-4 py-2">
          <PlanFormFields
            name={name}
            setName={setName}
            description={description}
            setDescription={setDescription}
            priceInr={priceInr}
            setPriceInr={setPriceInr}
            billingPeriod={billingPeriod}
            setBillingPeriod={setBillingPeriod}
            isActive={isActive}
            setIsActive={setIsActive}
            razorpayPlanId={razorpayPlanId}
            setRazorpayPlanId={setRazorpayPlanId}
            entitlementsJson={entitlementsJson}
            setEntitlementsJson={setEntitlementsJson}
            disabled={saving}
            showTier={false}
          />
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                "Save changes"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── New Plan Dialog ────────────────────────────────────────────────
function NewPlanDialog({
  token,
  onCreated,
}: {
  token: string;
  onCreated: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const [tier, setTier] = useState<Tier>("starter");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [priceInr, setPriceInr] = useState("0");
  const [billingPeriod, setBillingPeriod] = useState("monthly");
  const [isActive, setIsActive] = useState(true);
  const [razorpayPlanId, setRazorpayPlanId] = useState("");
  const [entitlementsJson, setEntitlementsJson] = useState("{}");

  function resetForm() {
    setTier("starter");
    setName("");
    setDescription("");
    setPriceInr("0");
    setBillingPeriod("monthly");
    setIsActive(true);
    setRazorpayPlanId("");
    setEntitlementsJson("{}");
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;

    let parsedEntitlements: Record<string, unknown>;
    try {
      parsedEntitlements = JSON.parse(entitlementsJson) as Record<string, unknown>;
    } catch {
      toast.error("Invalid JSON in Entitlements field. Please fix and try again.");
      return;
    }

    setSaving(true);
    try {
      const body: PlanWrite = {
        tier,
        name: name.trim(),
        description: description.trim() || null,
        price_inr: priceInr,
        billing_period: billingPeriod,
        is_active: isActive,
        razorpay_plan_id: razorpayPlanId.trim() || null,
        entitlements: parsedEntitlements,
      };
      await adminCreatePlan(token, body);
      toast.success("Plan created.");
      setOpen(false);
      resetForm();
      onCreated();
    } catch {
      // apiFetch already toasted
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) resetForm();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="mr-1.5 h-4 w-4" />
          New plan
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>New Plan</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleCreate} className="space-y-4 py-2">
          <PlanFormFields
            tier={tier}
            setTier={setTier}
            name={name}
            setName={setName}
            description={description}
            setDescription={setDescription}
            priceInr={priceInr}
            setPriceInr={setPriceInr}
            billingPeriod={billingPeriod}
            setBillingPeriod={setBillingPeriod}
            isActive={isActive}
            setIsActive={setIsActive}
            razorpayPlanId={razorpayPlanId}
            setRazorpayPlanId={setRazorpayPlanId}
            entitlementsJson={entitlementsJson}
            setEntitlementsJson={setEntitlementsJson}
            disabled={saving}
            showTier
          />
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving || !name.trim()}>
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating…
                </>
              ) : (
                "Create plan"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Shared plan form fields ────────────────────────────────────────────
interface PlanFormFieldsProps {
  tier?: Tier;
  setTier?: (v: Tier) => void;
  showTier: boolean;
  name: string;
  setName: (v: string) => void;
  description: string;
  setDescription: (v: string) => void;
  priceInr: string;
  setPriceInr: (v: string) => void;
  billingPeriod: string;
  setBillingPeriod: (v: string) => void;
  isActive: boolean;
  setIsActive: (v: boolean) => void;
  razorpayPlanId: string;
  setRazorpayPlanId: (v: string) => void;
  entitlementsJson: string;
  setEntitlementsJson: (v: string) => void;
  disabled: boolean;
}

function PlanFormFields({
  tier,
  setTier,
  showTier,
  name,
  setName,
  description,
  setDescription,
  priceInr,
  setPriceInr,
  billingPeriod,
  setBillingPeriod,
  isActive,
  setIsActive,
  razorpayPlanId,
  setRazorpayPlanId,
  entitlementsJson,
  setEntitlementsJson,
  disabled,
}: PlanFormFieldsProps) {
  return (
    <>
      {showTier && tier !== undefined && setTier && (
        <div className="space-y-1.5">
          <Label htmlFor="pf-tier">Tier *</Label>
          <Select
            value={tier}
            onValueChange={(v) => setTier(v as Tier)}
            disabled={disabled}
          >
            <SelectTrigger id="pf-tier">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TIER_OPTIONS.map((t) => (
                <SelectItem key={t} value={t} className="capitalize">
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="pf-name">Name *</Label>
        <Input
          id="pf-name"
          placeholder="e.g. Professional"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={disabled}
          required
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="pf-desc">Description</Label>
        <Input
          id="pf-desc"
          placeholder="Short description shown to customers"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={disabled}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="pf-price">Price (INR) *</Label>
          <Input
            id="pf-price"
            type="number"
            min="0"
            step="1"
            placeholder="0"
            value={priceInr}
            onChange={(e) => setPriceInr(e.target.value)}
            disabled={disabled}
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="pf-period">Billing period *</Label>
          <Select
            value={billingPeriod}
            onValueChange={setBillingPeriod}
            disabled={disabled}
          >
            <SelectTrigger id="pf-period">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="monthly">Monthly</SelectItem>
              <SelectItem value="quarterly">Quarterly</SelectItem>
              <SelectItem value="annual">Annual</SelectItem>
              <SelectItem value="one_time">One-time</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="pf-rzpid">Razorpay Plan ID</Label>
        <Input
          id="pf-rzpid"
          placeholder="plan_XXXXXXXXXXXXXXXX"
          value={razorpayPlanId}
          onChange={(e) => setRazorpayPlanId(e.target.value)}
          disabled={disabled}
          className="font-mono text-sm"
        />
        <p className="text-xs text-zinc-400">
          Required to enable real Razorpay checkout for this plan.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <Switch
          id="pf-active"
          checked={isActive}
          onCheckedChange={setIsActive}
          disabled={disabled}
          aria-label="Plan active"
        />
        <Label htmlFor="pf-active" className="cursor-pointer">
          Plan active (visible to tenants)
        </Label>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="pf-ent">Entitlements (JSON)</Label>
        <textarea
          id="pf-ent"
          rows={6}
          value={entitlementsJson}
          onChange={(e) => setEntitlementsJson(e.target.value)}
          disabled={disabled}
          spellCheck={false}
          className={cn(
            "w-full rounded-md border border-zinc-200 bg-transparent px-3 py-2 font-mono text-xs",
            "placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-brand-600",
            "dark:border-zinc-800 dark:text-zinc-100 dark:placeholder:text-zinc-600",
            "resize-y"
          )}
        />
        <p className="text-xs text-zinc-400">
          JSON object defining features and limits. Must be valid JSON.
        </p>
      </div>
    </>
  );
}

// ── Tenants Tab ──────────────────────────────────────────────────────────
function TenantsTab({ token }: { token: string }) {
  const [tenants, setTenants] = useState<PlatformTenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // per-row loading keyed by tenant id
  const [rowLoading, setRowLoading] = useState<Record<string, boolean>>({});

  const fetchTenants = useCallback(() => {
    setLoading(true);
    adminListTenants(token, { limit: 100 })
      .then(setTenants)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    fetchTenants();
  }, [fetchTenants]);

  async function handleStatusToggle(tenant: PlatformTenant) {
    setRowLoading((prev) => ({ ...prev, [tenant.id]: true }));
    try {
      if (tenant.status === "active") {
        await adminSuspendTenant(token, tenant.id);
        toast.success(`${tenant.name} suspended.`);
      } else {
        await adminActivateTenant(token, tenant.id);
        toast.success(`${tenant.name} activated.`);
      }
      fetchTenants();
    } catch {
      // apiFetch already toasted
    } finally {
      setRowLoading((prev) => {
        const next = { ...prev };
        delete next[tenant.id];
        return next;
      });
    }
  }

  if (loading) return <TableSkeleton rows={6} cols={4} />;
  if (error) return <TabError message={error} onRetry={fetchTenants} />;

  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        {tenants.length} tenant{tenants.length !== 1 ? "s" : ""} registered on the platform.
      </p>

      {tenants.length === 0 ? (
        <EmptyState icon={Users} message="No tenants yet." />
      ) : (
        <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tenants.map((tenant) => {
                const isInFlight = !!rowLoading[tenant.id];
                const isActive = tenant.status === "active";
                return (
                  <TableRow key={tenant.id}>
                    <TableCell>
                      <div className="font-medium">{tenant.name}</div>
                      <div className="text-xs font-mono text-zinc-400">
                        {tenant.id.slice(0, 8)}…
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={isActive ? "success" : "destructive"}
                        className="capitalize"
                      >
                        {tenant.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-zinc-500 text-sm whitespace-nowrap">
                      {formatDate(tenant.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      {isInFlight ? (
                        <Loader2 className="ml-auto h-4 w-4 animate-spin text-zinc-400" />
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          className={cn(
                            "h-7 px-2.5 text-xs",
                            isActive
                              ? "text-red-600 border-red-200 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/20"
                              : "text-emerald-600 border-emerald-200 hover:bg-emerald-50 dark:border-emerald-800 dark:text-emerald-400 dark:hover:bg-emerald-900/20"
                          )}
                          onClick={() => handleStatusToggle(tenant)}
                          aria-label={
                            isActive
                              ? `Suspend tenant ${tenant.name}`
                              : `Activate tenant ${tenant.name}`
                          }
                        >
                          {isActive ? "Suspend" : "Activate"}
                        </Button>
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

// ── Settings Tab ────────────────────────────────────────────────────────
function SettingsTab({ token }: { token: string }) {
  // initialising state for all known keys
  const [rows, setRows] = useState<Record<string, SettingRowState>>(() =>
    Object.fromEntries(
      SECRET_KEYS.map(({ key }) => [
        key,
        {
          currentValue: null,
          inputValue: "",
          visible: false,
          loading: true,
          saving: false,
        },
      ])
    )
  );

  // Load all settings concurrently on mount
  useEffect(() => {
    if (!token) return;
    SECRET_KEYS.forEach(({ key }) => {
      adminGetSetting(token, key)
        .then((setting: PlatformSetting) => {
          setRows((prev) => ({
            ...prev,
            [key]: {
              ...prev[key],
              currentValue: setting.value,
              inputValue: "", // never pre-fill — mask after save
              loading: false,
            },
          }));
        })
        .catch(() => {
          // key not yet set — treat as "Not set"
          setRows((prev) => ({
            ...prev,
            [key]: { ...prev[key], currentValue: null, loading: false },
          }));
        });
    });
  }, [token]);

  function updateRow(key: string, patch: Partial<SettingRowState>) {
    setRows((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));
  }

  async function handleSave(key: string) {
    const row = rows[key];
    if (!row || !row.inputValue.trim()) {
      toast.error("Enter a value before saving.");
      return;
    }
    updateRow(key, { saving: true });
    try {
      await adminSetSetting(token, key, {
        value: row.inputValue.trim(),
        is_secret: true,
      });
      toast.success("Secret saved and encrypted.");
      // After saving, mark as set but do NOT echo value back
      updateRow(key, {
        currentValue: "***", // masked sentinel
        inputValue: "",
        saving: false,
      });
    } catch {
      // apiFetch already toasted
      updateRow(key, { saving: false });
    }
  }

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      {/* Disclaimer */}
      <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-400">
        <strong className="font-semibold text-zinc-800 dark:text-zinc-200">
          Security note:
        </strong>{" "}
        Secrets are encrypted at rest; values are masked after saving. To rotate a key, enter the new value and save.
      </div>

      {/* Secret rows */}
      <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
        {SECRET_KEYS.map(({ key, label, description }) => {
          const row = rows[key];
          if (!row) return null;
          const isSet = !!row.currentValue;

          return (
            <div key={key} className="flex flex-col gap-3 py-5 sm:flex-row sm:items-start sm:gap-6">
              {/* Label + description */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
                    {label}
                  </p>
                  {row.loading ? (
                    <Skeleton className="h-4 w-14" />
                  ) : isSet ? (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="h-3 w-3" />
                      Set
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-zinc-400">
                      <CircleDashed className="h-3 w-3" />
                      Not set
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-xs text-zinc-400">{description}</p>
                <p className="mt-0.5 font-mono text-xs text-zinc-300 dark:text-zinc-700 select-all">
                  {key}
                </p>
              </div>

              {/* Input + action */}
              <div className="flex shrink-0 items-center gap-2 sm:w-72">
                <div className="relative flex-1">
                  <Input
                    type={row.visible ? "text" : "password"}
                    placeholder={isSet ? "Enter new value to rotate…" : "Enter value…"}
                    value={row.inputValue}
                    onChange={(e) => updateRow(key, { inputValue: e.target.value })}
                    disabled={row.saving || row.loading}
                    aria-label={`Value for ${label}`}
                    className="pr-9 font-mono text-sm"
                    autoComplete="off"
                  />
                  <button
                    type="button"
                    onClick={() => updateRow(key, { visible: !row.visible })}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 rounded"
                    aria-label={row.visible ? "Hide value" : "Show value"}
                    tabIndex={0}
                  >
                    {row.visible ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
                <Button
                  size="sm"
                  onClick={() => handleSave(key)}
                  disabled={row.saving || row.loading || !row.inputValue.trim()}
                  className="shrink-0"
                >
                  {row.saving ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    "Save"
                  )}
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface SettingRowState {
  currentValue: string | null; // null = "Not set"
  inputValue: string;
  visible: boolean;
  loading: boolean;
  saving: boolean;
}

// ── Shared helpers ────────────────────────────────────────────────────────
function TableSkeleton({ rows, cols }: { rows: number; cols: number }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <div className="p-4 space-y-3">
        {/* header row */}
        <div className={cn("grid gap-4", `grid-cols-${cols}`)}>
          {Array.from({ length: cols }).map((_, i) => (
            <Skeleton key={i} className="h-4 w-full" />
          ))}
        </div>
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}

function EmptyState({
  icon: Icon,
  message,
}: {
  icon: React.ElementType;
  message: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <Icon className="mb-3 h-10 w-10 text-zinc-300" />
      <p className="text-sm font-medium text-zinc-500">{message}</p>
    </div>
  );
}

function TabError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <AlertTriangle className="mb-3 h-10 w-10 text-red-400" />
      <h3 className="font-semibold">Failed to load</h3>
      <p className="mt-1 text-sm text-zinc-500">{message}</p>
      <Button size="sm" variant="outline" className="mt-4" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

// Needed for the overview skeleton
function OverviewSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardContent className="pt-6 space-y-3">
              <div className="flex justify-between">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-4 w-4 rounded" />
              </div>
              <Skeleton className="h-8 w-24" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-3">
              <Skeleton className="h-4 w-40" />
            </CardHeader>
            <CardContent className="space-y-2">
              {Array.from({ length: 4 }).map((_, j) => (
                <Skeleton key={j} className="h-6 w-full" />
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
