// Typed API client for the sVault backend.
// Maps the error envelope { error: { code, message, details, request_id } }
// to a thrown AppError, and shows sonner toasts on failure.
// The Supabase Bearer token is injected via withToken().

import { toast } from "sonner";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "https://svault.rstglobal.in/api/v1";

// ── Error type ──────────────────────────────────────────────────────────

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

// ── Fetch core ──────────────────────────────────────────────────────────

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

// ── Types (derived from backend Pydantic schemas) ────────────────────────────

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
  created_at: string;
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

// ── Endpoint functions (token-aware, used from Client Components) ─────────────

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

// ── Billing: subscribe ─────────────────────────────────────────────────

export interface SubscribeResponse {
  subscription_id: string;
  status: string;
  plan_id: string;
  razorpay_subscription_id: string | null;
  short_url: string | null;
}

export const subscribe = (token: string, planId: string) =>
  apiFetch<SubscribeResponse>("/billing/subscribe", {
    method: "POST",
    body: JSON.stringify({ plan_id: planId }),
    token,
  });

// ── Documents ─────────────────────────────────────────────────────────

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

// ── Users / Invitations ──────────────────────────────────────────────

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

// ── Ask sVault (AI / RAG) ─────────────────────────────────────────────

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

// ── Approvals ─────────────────────────────────────────────────────────

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
