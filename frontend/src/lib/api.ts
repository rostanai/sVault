// Typed API client for the sVault backend.
// Maps the error envelope { error: { code, message, details, request_id } }
// to a thrown AppError, and shows sonner toasts on failure.
// The Supabase Bearer token is injected via withToken().

import { toast } from "sonner";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "https://svault.rstglobal.in/api/v1";

// Error type

export class AppError extends Error {
  code: string;
  requestId?: string;
  details?: unknown;
  constructor(
    code: string,
    message: string,
    requestId?: string,
    details?: unknown
  ) {
    super(message);
    this.name = "AppError";
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

// Fetch core

async function apiFetch<T>(
  path: string,
  init?: RequestInit & { token?: string; silent?: boolean }
): Promise<T> {
  const { token, silent, ...rest } = init ?? {};

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(rest.headers as Record<string, string> | undefined),
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    let code = "internal_error";
    let message = "Request failed";
    let requestId: string | undefined;
    let details: unknown;
    try {
      const body = await res.json();
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
        requestId = body.error.request_id;
        details = body.error.details;
      }
    } catch {
      /* non-JSON body */
    }
    const err = new AppError(code, message, requestId, details);
    if (!silent) {
      toast.error(message, {
        description: requestId ? `Request ID: ${requestId}` : undefined,
        duration: 6000,
      });
    }
    throw err;
  }

  return res.json() as Promise<T>;
}

// Helper: build a fetch wrapper with a static Bearer token
export function withToken(token: string) {
  return function fetcher<T>(path: string, init?: RequestInit): Promise<T> {
    return apiFetch<T>(path, { ...init, token });
  };
}

// Types (derived from backend Pydantic schemas)

export interface Health {
  status: string;
  service: string;
  env: string;
}

export interface MeResponse {
  user_id: string;
  tenant_id: string | null;
  org_id: string | null;
  role: string;
  is_super_admin: boolean;
  email: string | null;
}

export interface OnboardRequest {
  company_name: string;
  full_name?: string;
}

export interface OnboardResponse {
  tenant_id: string;
  org_id: string;
  role: string;
  trial_ends_at: string;
  note: string;
}

export interface OrgRead {
  id: string;
  tenant_id: string;
  parent_org_id: string | null;
  name: string;
  org_type: string;
  gstin: string | null;
  is_active: boolean;
}

// Dashboard
export interface DashboardTotals {
  policies: number;
  sum_insured_inr: string;
  premium_inr: string;
  lapsed: number;
}

export interface ExpiringBuckets {
  next_30: number;
  next_60: number;
  next_90: number;
}

export interface CategoryCount {
  category: string;
  count: number;
}

export interface UpcomingPolicy {
  id: string;
  title: string;
  category: string;
  expiry_date: string | null;
  status: string;
  days_left: number | null;
}

export interface DashboardResponse {
  totals: DashboardTotals;
  status_counts: Record<string, number>;
  expiring: ExpiringBuckets;
  by_category: CategoryCount[];
  upcoming: UpcomingPolicy[];
}

// Policies
export type PolicyCategory =
  | "vehicle"
  | "machinery"
  | "plant"
  | "factory_property"
  | "employees_group_health"
  | "key_person"
  | "stock_raw_material"
  | "stock_finished_goods"
  | "other";

export type PolicyStatus =
  | "draft"
  | "pending_approval"
  | "active"
  | "expiring"
  | "lapsed"
  | "renewed"
  | "cancelled";

export interface PolicyRead {
  id: string;
  org_id: string;
  category: string;
  title: string;
  policy_number: string | null;
  provider_id: string | null;
  owner_id: string | null;
  sum_insured_inr: string | null;
  premium_inr: string | null;
  gst_inr: string | null;
  inception_date: string | null;
  expiry_date: string | null;
  renewal_date: string | null;
  status: string;
  custom_fields: Record<string, string>;
  created_at: string;
}

export interface PolicyUpdate {
  title?: string;
  policy_number?: string | null;
  provider_id?: string | null;
  sum_insured_inr?: string | null;
  premium_inr?: string | null;
  gst_inr?: string | null;
  inception_date?: string | null;
  expiry_date?: string | null;
  renewal_date?: string | null;
  status?: string;
  custom_fields?: Record<string, string>;
}

export interface PolicyCreate {
  org_id: string;
  category: PolicyCategory;
  title: string;
  policy_number?: string;
  provider_id?: string;
  sum_insured_inr?: string;
  premium_inr?: string;
  gst_inr?: string;
  inception_date?: string;
  expiry_date?: string;
  renewal_date?: string;
}

export interface PoliciesListResponse {
  items: PolicyRead[];
  total: number;
  offset: number;
  limit: number;
}

// Billing / Plans
export interface PlanRead {
  id: string;
  tier: string;
  name: string;
  description: string | null;
  price_inr: string;
  billing_period: string;
  is_active: boolean;
  entitlements: Record<string, unknown>;
  razorpay_plan_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubscriptionRead {
  id: string;
  tenant_id: string;
  plan_id: string | null;
  status: string;
  trial_ends_at: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  razorpay_subscription_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubscriptionWithEntitlements {
  subscription: SubscriptionRead | null;
  entitlements: Record<string, unknown>;
}

export interface InvoiceRead {
  id: string;
  amount_inr: string;
  gst_inr: string;
  status: string;
  issued_at: string;
  paid_at: string | null;
  pdf_url: string | null;
  razorpay_invoice_id: string | null;
}

// Endpoint functions (token-aware, used from Client Components)

export const getHealth = () => apiFetch<Health>("/health");

export const getMe = (token: string) =>
  apiFetch<MeResponse>("/auth/me", { token, silent: true });

export const postOnboard = (token: string, body: OnboardRequest) =>
  apiFetch<OnboardResponse>("/auth/onboard", {
    method: "POST",
    body: JSON.stringify(body),
    token,
  });

export const getOrgs = (token: string) =>
  apiFetch<OrgRead[]>("/orgs", { token });

export const getDashboard = (token: string) =>
  apiFetch<DashboardResponse>("/dashboard", { token });

export const getPolicies = (
  token: string,
  params?: {
    category?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }
) => {
  const qs = new URLSearchParams();
  if (params?.category) qs.set("category", params.category);
  if (params?.status) qs.set("status", params.status);
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<PolicyRead[]>(`/policies${query}`, { token });
};

export const getPolicy = (token: string, id: string) =>
  apiFetch<PolicyRead>(`/policies/${id}`, { token });

export const createPolicy = (token: string, body: PolicyCreate) =>
  apiFetch<PolicyRead>("/policies", {
    method: "POST",
    body: JSON.stringify(body),
    token,
  });

export const getPlans = (token: string) =>
  apiFetch<PlanRead[]>("/plans", { token });

export const getSubscription = (token: string) =>
  apiFetch<SubscriptionWithEntitlements>("/billing/subscription", { token });

export const getInvoices = (token: string) =>
  apiFetch<InvoiceRead[]>("/billing/invoices", { token, silent: true });

// Billing: subscribe

export interface SubscribeResponse {
  subscription_id: string;
  status: string;
  plan_id: string;
  razorpay_subscription_id: string | null;
  short_url: string | null;
  /** false = activated immediately (no Razorpay); true = open checkout to pay. */
  payment_required: boolean;
}

export const subscribe = (token: string, planId: string) =>
  apiFetch<SubscribeResponse>("/billing/subscribe", {
    method: "POST",
    body: JSON.stringify({ plan_id: planId }),
    token,
  });

// Documents

export type DocType =
  | "policy"
  | "schedule"
  | "endorsement"
  | "invoice"
  | "claim"
  | "other";

export interface UploadUrlResponse {
  upload_url: string;
  storage_path: string;
  note?: string;
}

export interface DocumentRead {
  id: string;
  file_name: string;
  doc_type: string;
  mime_type: string | null;
  size_bytes: number | null;
  version: number;
  created_at: string;
  download_url: string;
}

export const getDocumentUploadUrl = (
  token: string,
  policyId: string,
  body: { file_name: string; content_type: string }
) =>
  apiFetch<UploadUrlResponse>(
    `/policies/${policyId}/documents/upload-url`,
    {
      method: "POST",
      body: JSON.stringify(body),
      token,
    }
  );

// Raw PUT to Supabase Storage — no auth header, no JSON wrapper.
export async function uploadFileToStorage(
  uploadUrl: string,
  file: File
): Promise<void> {
  const res = await fetch(uploadUrl, {
    method: "PUT",
    body: file,
    headers: { "Content-Type": file.type },
  });
  if (!res.ok) {
    throw new Error(`Storage upload failed: ${res.status}`);
  }
}

export const recordDocument = (
  token: string,
  policyId: string,
  body: {
    storage_path: string;
    file_name: string;
    content_type: string;
    size_bytes: number;
    doc_type: DocType;
  }
) =>
  apiFetch<DocumentRead>(`/policies/${policyId}/documents`, {
    method: "POST",
    body: JSON.stringify(body),
    token,
  });

export const listDocuments = (token: string, policyId: string) =>
  apiFetch<DocumentRead[]>(`/policies/${policyId}/documents`, { token });

export const deleteDocument = (token: string, documentId: string) =>
  apiFetch<void>(`/documents/${documentId}`, {
    method: "DELETE",
    token,
    silent: true,
  });

// Users / Invitations

export interface ProfileRead {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  org_id: string | null;
  is_active: boolean;
}

export interface RoleUpdate {
  role: string;
  is_active?: boolean;
}

export interface InvitationRead {
  id: string;
  email: string;
  role: string;
  org_id: string | null;
  expires_at: string;
  token?: string;
}

export const getUsers = (token: string) =>
  apiFetch<ProfileRead[]>("/users", { token });

export const updateUser = (token: string, userId: string, body: RoleUpdate) =>
  apiFetch<ProfileRead>(`/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
    token,
  });

export const getInvitations = (token: string) =>
  apiFetch<InvitationRead[]>("/invitations", { token, silent: true });

export const createInvitation = (
  token: string,
  body: { email: string; role: string; org_id?: string }
) =>
  apiFetch<InvitationRead>("/invitations", {
    method: "POST",
    body: JSON.stringify(body),
    token,
  });

// Ask sVault (AI / RAG)

export interface AskSource {
  policy_id: string;
  snippet: string;
}

export interface AskResponse {
  answer: string;
  sources: AskSource[];
}

export interface IngestResponse {
  chunks: number;
}

/** Ask a natural-language question grounded in the tenant's policy documents. */
export const askSvault = (token: string, question: string) =>
  apiFetch<AskResponse>("/ask", {
    method: "POST",
    body: JSON.stringify({ question }),
    token,
  });

/** Index a policy document for AI retrieval (idempotent). Returns chunk count. */
export const ingestDocument = (
  token: string,
  policyId: string,
  documentId: string
) =>
  apiFetch<IngestResponse>(
    `/policies/${policyId}/documents/${documentId}/ingest`,
    { method: "POST", token }
  );

// Approvals

export type ApprovalActionType =
  | "renewal"
  | "new_policy"
  | "vendor_finalization"
  | "high_value_premium"
  | "other";

export type ApprovalStatus = "pending" | "approved" | "rejected" | "cancelled";

export interface ApprovalRead {
  id: string;
  tenant_id: string;
  org_id: string | null;
  action_type: string;
  entity_type: string;
  entity_id: string;
  amount_inr: string | null;
  status: string;
  requested_by: string | null;
  approver_id: string | null;
  is_self_approval: boolean;
  reason: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface ApprovalCreate {
  action_type: ApprovalActionType;
  entity_type: string;
  entity_id: string;
  amount_inr?: string;
}

export const getApprovals = (
  token: string,
  params?: { status?: ApprovalStatus; limit?: number; offset?: number }
) => {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<ApprovalRead[]>(`/approvals${query}`, { token });
};

export const createApproval = (token: string, body: ApprovalCreate) =>
  apiFetch<ApprovalRead>("/approvals", {
    method: "POST",
    body: JSON.stringify(body),
    token,
  });

export const approveApproval = (
  token: string,
  approvalId: string,
  reason?: string
) =>
  apiFetch<ApprovalRead>(`/approvals/${approvalId}/approve`, {
    method: "POST",
    body: JSON.stringify({ reason: reason ?? null }),
    token,
  });

export const rejectApproval = (
  token: string,
  approvalId: string,
  reason?: string
) =>
  apiFetch<ApprovalRead>(`/approvals/${approvalId}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason: reason ?? null }),
    token,
  });

// Providers (insurers / vendors)

export interface ProviderRead {
  id: string;
  name: string;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
}

export interface ProviderCreate {
  name: string;
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  notes?: string;
}

export const getProviders = (token: string) =>
  apiFetch<ProviderRead[]>("/providers", { token });

export const createProvider = (token: string, body: ProviderCreate) =>
  apiFetch<ProviderRead>("/providers", {
    method: "POST",
    body: JSON.stringify(body),
    token,
  });

// Alerts (renewal notifications)

export type AlertChannel = "whatsapp" | "email" | "sms" | "telegram";

export interface AlertRead {
  id: string;
  policy_id: string;
  channel: string;
  lead_day: number;
  scheduled_for: string;
  status: string;
  acknowledged_at: string | null;
}

export interface AlertRuleRead {
  id: string | null;
  policy_id: string | null;
  lead_days: number[];
  channels: string[];
  escalate: boolean;
  is_active: boolean;
}

export interface AlertRuleUpdate {
  lead_days?: number[];
  channels?: AlertChannel[];
  escalate?: boolean;
  is_active?: boolean;
}

export const getAlerts = (
  token: string,
  params?: { status?: string; limit?: number; offset?: number }
) => {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<AlertRead[]>(`/alerts${query}`, { token });
};

export const acknowledgeAlert = (token: string, alertId: string) =>
  apiFetch<{ id: string; status: string }>(`/alerts/${alertId}/ack`, {
    method: "POST",
    token,
  });

export const getAlertRule = (token: string, policyId: string) =>
  apiFetch<AlertRuleRead>(`/policies/${policyId}/alert-rule`, { token });

export const setAlertRule = (
  token: string,
  policyId: string,
  body: AlertRuleUpdate
) =>
  apiFetch<AlertRuleRead>(`/policies/${policyId}/alert-rule`, {
    method: "PUT",
    body: JSON.stringify(body),
    token,
  });

// ── AI Policy Intake (auto-extract from a document) ──────────────────────────

export interface PolicyExtraction {
  category: PolicyCategory | null;
  title: string | null;
  policy_number: string | null;
  insurer_name: string | null;
  sum_insured_inr: string | null;
  premium_inr: string | null;
  gst_inr: string | null;
  inception_date: string | null; // YYYY-MM-DD
  expiry_date: string | null; // YYYY-MM-DD
  extracted_text_chars: number;
  notes: string | null;
}

/**
 * Upload a policy PDF and let sVault AI extract structured fields for review.
 * Multipart upload — does NOT persist anything; the caller reviews then creates
 * the policy via createPolicy. Returns all-null fields + a note for scanned/
 * unreadable documents (OCR not yet supported).
 */
export async function extractPolicyFromDocument(
  token: string,
  file: File
): Promise<PolicyExtraction> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/policies/extract`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` }, // no Content-Type — browser sets multipart boundary
    body: form,
    cache: "no-store",
  });
  if (!res.ok) {
    let code = "internal_error";
    let message = "Extraction failed";
    let requestId: string | undefined;
    try {
      const body = await res.json();
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
        requestId = body.error.request_id;
      }
    } catch {
      /* non-JSON */
    }
    toast.error(message, {
      description: requestId ? `Request ID: ${requestId}` : undefined,
      duration: 6000,
    });
    throw new AppError(code, message, requestId);
  }
  return res.json() as Promise<PolicyExtraction>;
}

// ── Developer API keys ──────────────────────────────────────────────

export interface ApiKeyRead {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface ApiKeyCreated extends ApiKeyRead {
  /** Full plaintext key — shown ONCE on creation, never again. */
  plaintext_key: string;
}

export const getApiKeys = (token: string) =>
  apiFetch<ApiKeyRead[]>("/api-keys", { token });

export const createApiKey = (
  token: string,
  body: { name: string; scopes?: string[]; expires_in_days?: number }
) =>
  apiFetch<ApiKeyCreated>("/api-keys", {
    method: "POST",
    body: JSON.stringify(body),
    token,
  });

export const revokeApiKey = (token: string, keyId: string) =>
  apiFetch<{ id: string; revoked_at: string }>(`/api-keys/${keyId}`, {
    method: "DELETE",
    token,
    silent: true,
  });

// ── Super Admin / Platform (super_admin only) ───────────────────────────────────

export interface PlatformTenant {
  id: string;
  name: string;
  status: string;
  created_at: string;
}

export interface PlatformSetting {
  key: string;
  value: string | null; // masked for secrets
  is_secret: boolean;
  updated_at: string | null;
}

export interface PlatformAnalytics {
  tenants: { total: number; active: number; suspended: number };
  subscriptions: Record<string, number>; // by status: trialing/active/past_due/cancelled/expired
  by_tier: { tier: string; count: number }[];
  mrr_inr: string;
}

export interface PlanWrite {
  tier?: string;
  name?: string;
  description?: string | null;
  price_inr?: string;
  billing_period?: string;
  is_active?: boolean;
  entitlements?: Record<string, unknown>;
  razorpay_plan_id?: string | null;
}

// Plans (platform view — includes inactive)
export const adminListPlans = (token: string) =>
  apiFetch<PlanRead[]>("/platform/plans", { token });

export const adminCreatePlan = (token: string, body: PlanWrite) =>
  apiFetch<PlanRead>("/platform/plans", {
    method: "POST",
    body: JSON.stringify(body),
    token,
  });

export const adminUpdatePlan = (token: string, planId: string, body: PlanWrite) =>
  apiFetch<PlanRead>(`/platform/plans/${planId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
    token,
  });

// Tenants
export const adminListTenants = (
  token: string,
  params?: { limit?: number; offset?: number }
) => {
  const qs = new URLSearchParams();
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<PlatformTenant[]>(`/platform/tenants${query}`, { token });
};

export const adminSuspendTenant = (token: string, tenantId: string) =>
  apiFetch<PlatformTenant>(`/platform/tenants/${tenantId}/suspend`, {
    method: "POST",
    token,
  });

export const adminActivateTenant = (token: string, tenantId: string) =>
  apiFetch<PlatformTenant>(`/platform/tenants/${tenantId}/activate`, {
    method: "POST",
    token,
  });

// Global settings / secrets
export const adminGetSetting = (token: string, key: string) =>
  apiFetch<PlatformSetting>(`/platform/settings/${key}`, { token, silent: true });

export const adminSetSetting = (
  token: string,
  key: string,
  body: { value: string; is_secret?: boolean }
) =>
  apiFetch<PlatformSetting>(`/platform/settings/${key}`, {
    method: "PUT",
    body: JSON.stringify(body),
    token,
  });

// Platform analytics (overview)
export const adminGetAnalytics = (token: string) =>
  apiFetch<PlatformAnalytics>("/platform/analytics", { token });

// ── Reports + Excel import/export ───────────────────────────────────────────────

export interface RenewalReportRow {
  policy_id: string;
  title: string;
  category: string;
  provider_name: string | null;
  expiry_date: string | null;
  days_left: number | null;
  premium_inr: string | null;
  sum_insured_inr: string | null;
  status: string;
}

export interface ImportResult {
  created: number;
  skipped: number;
  errors: { row: number; message: string }[];
}

/** Renewal report rows (policies in a forward expiry window). */
export const getRenewalReport = (
  token: string,
  params?: { window_days?: number }
) => {
  const qs = new URLSearchParams();
  if (params?.window_days != null) qs.set("window_days", String(params.window_days));
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<RenewalReportRow[]>(`/reports/renewals${query}`, { token });
};

/** Fetch an authed file (CSV/XLSX) and trigger a browser download. */
export async function downloadAuthed(
  token: string,
  path: string,
  fallbackName: string
): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) {
    let message = "Download failed";
    try {
      const body = await res.json();
      message = body?.error?.message ?? message;
    } catch {
      /* binary/empty body */
    }
    toast.error(message);
    throw new AppError("internal_error", message);
  }
  const cd = res.headers.get("content-disposition") ?? "";
  const match = cd.match(/filename="?([^";]+)"?/);
  const filename = match?.[1] ?? fallbackName;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Export all policies as CSV or XLSX (triggers download). */
export const exportPolicies = (token: string, format: "csv" | "xlsx") =>
  downloadAuthed(token, `/policies/export?format=${format}`, `policies.${format}`);

/** Export the renewal report as CSV or XLSX (triggers download). */
export const exportRenewalReport = (
  token: string,
  format: "csv" | "xlsx",
  windowDays?: number
) =>
  downloadAuthed(
    token,
    `/reports/renewals/export?format=${format}${windowDays != null ? `&window_days=${windowDays}` : ""}`,
    `renewals.${format}`
  );

/** Bulk-import policies from an .xlsx/.csv file (multipart). */
export async function importPolicies(
  token: string,
  file: File
): Promise<ImportResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/policies/import`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
    cache: "no-store",
  });
  if (!res.ok) {
    let code = "internal_error";
    let message = "Import failed";
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? message;
    } catch {
      /* non-JSON */
    }
    toast.error(message);
    throw new AppError(code, message);
  }
  return res.json() as Promise<ImportResult>;
}

// ── Alert actions (snooze / mark renewed) ───────────────────────────────────────

export const snoozeAlert = (token: string, alertId: string, days: number) =>
  apiFetch<{ id: string; status: string; scheduled_for: string }>(
    `/alerts/${alertId}/snooze`,
    { method: "POST", body: JSON.stringify({ days }), token }
  );

/** Mark a policy renewed (sets status=renewed, cancels its pending alerts). */
export const markPolicyRenewed = (token: string, policyId: string) =>
  apiFetch<PolicyRead>(`/policies/${policyId}/mark-renewed`, {
    method: "POST",
    token,
  });

// ── Document library (all documents across policies) ────────────────────────────

export interface DocumentLibraryItem {
  id: string;
  file_name: string;
  doc_type: string;
  mime_type: string | null;
  size_bytes: number | null;
  created_at: string;
  download_url: string;
  policy_id: string;
  policy_title: string;
  policy_category: string;
  snippet: string | null; // matched content snippet when searching inside documents
}

export const getAllDocuments = (
  token: string,
  params?: { search?: string; doc_type?: string; limit?: number; offset?: number }
) => {
  const qs = new URLSearchParams();
  if (params?.search) qs.set("search", params.search);
  if (params?.doc_type) qs.set("doc_type", params.doc_type);
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<DocumentLibraryItem[]>(`/documents${query}`, { token });
};

// ── Notifications (in-app bell) ─────────────────────────────────────────────────

export interface NotificationItem {
  id: string;
  type: string; // "alert" | "approval"
  title: string;
  subtitle: string | null;
  href: string;
  created_at: string;
}

export interface NotificationFeed {
  unread_count: number;
  items: NotificationItem[];
}

export const getNotifications = (token: string) =>
  apiFetch<NotificationFeed>("/notifications", { token, silent: true });

// ── Subscription lifecycle (cancel / pause / resume) ────────────────────────────

export const cancelSubscription = (token: string) =>
  apiFetch<SubscriptionRead>("/billing/cancel", { method: "POST", token });

export const pauseSubscription = (token: string) =>
  apiFetch<SubscriptionRead>("/billing/pause", { method: "POST", token });

export const resumeSubscription = (token: string) =>
  apiFetch<SubscriptionRead>("/billing/resume", { method: "POST", token });

// ── Policy renewal (creates next-year linked policy) ────────────────────────────

export interface RenewPolicyRequest {
  expiry_date: string; // new term expiry (YYYY-MM-DD)
  renewal_date?: string;
  inception_date?: string;
  premium_inr?: string;
  gst_inr?: string;
  sum_insured_inr?: string;
  policy_number?: string;
}

/** Renew a policy: marks the old one renewed and creates a linked new-term policy. */
export const renewPolicy = (
  token: string,
  policyId: string,
  body: RenewPolicyRequest
) =>
  apiFetch<PolicyRead>(`/policies/${policyId}/renew`, {
    method: "POST",
    body: JSON.stringify(body),
    token,
  });

// ── Outbound webhooks (developer integration) ───────────────────────────────────

export interface WebhookRead {
  id: string;
  url: string;
  events: string[];
  is_active: boolean;
  created_at: string;
}

export interface WebhookCreated extends WebhookRead {
  secret: string; // shown once on creation
}

export interface WebhookCreate {
  url: string;
  events: string[];
}

export const getWebhooks = (token: string) =>
  apiFetch<WebhookRead[]>("/webhooks", { token });

export const createWebhook = (token: string, body: WebhookCreate) =>
  apiFetch<WebhookCreated>("/webhooks", {
    method: "POST",
    body: JSON.stringify(body),
    token,
  });

export const deleteWebhook = (token: string, webhookId: string) =>
  apiFetch<void>(`/webhooks/${webhookId}`, {
    method: "DELETE",
    token,
    silent: true,
  });

export const testWebhook = (token: string, webhookId: string) =>
  apiFetch<{ delivered: boolean; status_code: number | null }>(
    `/webhooks/${webhookId}/test`,
    { method: "POST", token }
  );

// ── Plan usage / limits (metering + gating) ─────────────────────────────────────

export interface UsageMetric {
  used: number;
  limit: number; // -1 = unlimited
}

export interface UsageResponse {
  plan_tier: string;
  status: string;
  usage: Record<string, UsageMetric>; // policies, users, documents, alerts_month
}

export const getUsage = (token: string) =>
  apiFetch<UsageResponse>("/billing/usage", { token });

// ── Onboarding status (first-run checklist) ─────────────────────────────────────

export interface OnboardingStep {
  key: string;
  label: string;
  description: string;
  done: boolean;
  href: string;
}

export interface OnboardingStatus {
  steps: OnboardingStep[];
  complete: boolean;
  completed_count: number;
  total: number;
}

export const getOnboardingStatus = (token: string) =>
  apiFetch<OnboardingStatus>("/onboarding/status", { token, silent: true });

// ── Notification history (full feed page) ───────────────────────────────────────

export const getNotificationHistory = (
  token: string,
  params?: { limit?: number; offset?: number }
) => {
  const qs = new URLSearchParams();
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<NotificationItem[]>(`/notifications/history${query}`, { token });
};

// ── Calendar (.ics) — renewal/expiry feed ───────────────────────────────────────

/** Download an iCalendar (.ics) file of all policy expiry/renewal dates. */
export const downloadCalendar = (token: string) =>
  downloadAuthed(token, "/calendar.ics", "svault-renewals.ics");

// ── Provider detail + contact log ───────────────────────────────────────────────

export interface ProviderUpdate {
  name?: string;
  contact_name?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  notes?: string | null;
}

export interface ProviderContact {
  id: string;
  provider_id: string;
  kind: string; // call | email | meeting | note
  subject: string | null;
  note: string | null;
  contacted_at: string;
  created_by: string | null;
  created_at: string;
}

export interface ProviderContactCreate {
  kind: string;
  subject?: string;
  note?: string;
  contacted_at?: string;
}

export const getProvider = (token: string, providerId: string) =>
  apiFetch<ProviderRead>(`/providers/${providerId}`, { token });

export const updateProvider = (
  token: string,
  providerId: string,
  body: ProviderUpdate
) =>
  apiFetch<ProviderRead>(`/providers/${providerId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
    token,
  });

export const getProviderContacts = (token: string, providerId: string) =>
  apiFetch<ProviderContact[]>(`/providers/${providerId}/contacts`, { token });

export const addProviderContact = (
  token: string,
  providerId: string,
  body: ProviderContactCreate
) =>
  apiFetch<ProviderContact>(`/providers/${providerId}/contacts`, {
    method: "POST",
    body: JSON.stringify(body),
    token,
  });

export const deleteProviderContact = (token: string, contactId: string) =>
  apiFetch<void>(`/provider-contacts/${contactId}`, {
    method: "DELETE",
    token,
    silent: true,
  });

// ── Policy installments / payment tracking ──────────────────────────────────────

export interface Installment {
  id: string;
  policy_id: string;
  amount_inr: string;
  due_date: string;
  status: string; // pending | paid
  paid_at: string | null;
  note: string | null;
  created_at: string;
}

export interface InstallmentCreate {
  amount_inr: string;
  due_date: string;
  note?: string;
}

export const getInstallments = (token: string, policyId: string) =>
  apiFetch<Installment[]>(`/policies/${policyId}/installments`, { token });

export const addInstallment = (
  token: string,
  policyId: string,
  body: InstallmentCreate
) =>
  apiFetch<Installment>(`/policies/${policyId}/installments`, {
    method: "POST",
    body: JSON.stringify(body),
    token,
  });

export const markInstallmentPaid = (token: string, installmentId: string) =>
  apiFetch<Installment>(`/installments/${installmentId}/pay`, {
    method: "POST",
    token,
  });

export const deleteInstallment = (token: string, installmentId: string) =>
  apiFetch<void>(`/installments/${installmentId}`, {
    method: "DELETE",
    token,
    silent: true,
  });

// ── Consolidated group dashboard (parent rolls up subsidiaries) ─────────────────

export interface OrgRollup {
  org_id: string;
  org_name: string;
  policies: number;
  sum_insured_inr: string;
  premium_inr: string;
  expiring_30: number;
}

export interface GroupDashboardResponse {
  totals: DashboardTotals;
  by_org: OrgRollup[];
}

export const getGroupDashboard = (token: string) =>
  apiFetch<GroupDashboardResponse>("/dashboard/group", { token });

// ── Policy edit (standard fields + custom fields) ───────────────────────────────

export const updatePolicy = (
  token: string,
  policyId: string,
  body: PolicyUpdate
) =>
  apiFetch<PolicyRead>(`/policies/${policyId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
    token,
  });

// ── DPDP / account data export ──────────────────────────────────────────────────

/** Download a JSON export of all the tenant's data (DPDP data-principal request). */
export const downloadDataExport = (token: string) =>
  downloadAuthed(token, "/account/export", "svault-data-export.json");

// ── Weekly renewal digest (send now) ────────────────────────────────────────────

/** Send the current weekly renewal digest email to the caller (test/on-demand). */
export const sendDigestNow = (token: string) =>
  apiFetch<{ sent: boolean; recipient: string | null; policies: number }>(
    "/digests/send-me",
    { method: "POST", token }
  );

// ── Claims ──────────────────────────────────────────────────────────────────────

export type ClaimStatus =
  | "draft"
  | "reported"
  | "under_review"
  | "approved"
  | "rejected"
  | "settled"
  | "closed";

export interface ClaimRead {
  id: string;
  policy_id: string;
  org_id: string | null;
  claim_number: string | null;
  status: string;
  claim_amount_inr: string | null;
  approved_amount_inr: string | null;
  incident_date: string | null;
  reported_date: string | null;
  description: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  policy_title?: string | null; // enriched on list
}

export interface ClaimCreate {
  policy_id: string;
  claim_number?: string;
  claim_amount_inr?: string;
  incident_date?: string;
  description?: string;
}

export interface ClaimUpdate {
  status?: ClaimStatus;
  claim_number?: string;
  claim_amount_inr?: string;
  approved_amount_inr?: string;
  incident_date?: string;
  description?: string;
  note?: string; // optional note logged with a status change
}

export interface ClaimEvent {
  id: string;
  claim_id: string;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  note: string | null;
  created_by: string | null;
  created_at: string;
}

export const getClaims = (
  token: string,
  params?: { status?: ClaimStatus; policy_id?: string; limit?: number; offset?: number }
) => {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.policy_id) qs.set("policy_id", params.policy_id);
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<ClaimRead[]>(`/claims${query}`, { token });
};

export const getClaim = (token: string, claimId: string) =>
  apiFetch<ClaimRead>(`/claims/${claimId}`, { token });

export const createClaim = (token: string, body: ClaimCreate) =>
  apiFetch<ClaimRead>("/claims", {
    method: "POST",
    body: JSON.stringify(body),
    token,
  });

export const updateClaim = (token: string, claimId: string, body: ClaimUpdate) =>
  apiFetch<ClaimRead>(`/claims/${claimId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
    token,
  });

export const getClaimEvents = (token: string, claimId: string) =>
  apiFetch<ClaimEvent[]>(`/claims/${claimId}/events`, { token });

export const getPolicyClaims = (token: string, policyId: string) =>
  apiFetch<ClaimRead[]>(`/policies/${policyId}/claims`, { token });
