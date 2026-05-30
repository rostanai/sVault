// Minimal typed API client. Maps the backend error envelope
// ({ error: { code, message, details, request_id } }) to a typed AppError.
// Expanded with auth headers + endpoints in later milestones.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1";

export class AppError extends Error {
  code: string;
  requestId?: string;
  details?: unknown;
  constructor(code: string, message: string, requestId?: string, details?: unknown) {
    super(message);
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
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
      /* non-JSON error */
    }
    throw new AppError(code, message, requestId, details);
  }
  return res.json() as Promise<T>;
}

export interface Health {
  status: string;
  service: string;
  env: string;
}

export const getHealth = () => apiFetch<Health>("/health");
