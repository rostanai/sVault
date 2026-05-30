"""Razorpay HTTP client — Plans, Subscriptions, webhook signature verification.

Uses httpx with HTTP Basic Auth (key_id:key_secret).
All outbound calls use a 10-second timeout and raise AppError(upstream_error) on failure
so callers don't need to handle httpx exceptions directly.

If keys are not configured, operations raise AppError(internal_error) — never silently
skip billing.

Signature verification (verify_webhook_signature) is a pure function — no I/O, fully
unit-testable without mocking.
"""
from __future__ import annotations

import hashlib
import hmac

import httpx

from app.core.config import settings
from app.core.errors import AppError, ErrorCode

_BASE = "https://api.razorpay.com/v1"
_TIMEOUT = 10.0


def _auth() -> tuple[str, str]:
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise AppError(ErrorCode.internal_error, "Razorpay API keys not configured")
    return (settings.razorpay_key_id, settings.razorpay_key_secret)


async def _post(path: str, body: dict) -> dict:
    auth = _auth()
    try:
        async with httpx.AsyncClient(auth=auth, timeout=_TIMEOUT) as client:
            resp = await client.post(f"{_BASE}{path}", json=body)
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException as exc:
        raise AppError(ErrorCode.upstream_error, "Razorpay request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise AppError(
            ErrorCode.upstream_error,
            f"Razorpay error {exc.response.status_code}",
            details=exc.response.text,
        ) from exc
    except httpx.RequestError as exc:
        raise AppError(ErrorCode.upstream_error, "Razorpay request failed") from exc


async def _get(path: str) -> dict:
    auth = _auth()
    try:
        async with httpx.AsyncClient(auth=auth, timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_BASE}{path}")
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException as exc:
        raise AppError(ErrorCode.upstream_error, "Razorpay request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise AppError(
            ErrorCode.upstream_error,
            f"Razorpay error {exc.response.status_code}",
            details=exc.response.text,
        ) from exc
    except httpx.RequestError as exc:
        raise AppError(ErrorCode.upstream_error, "Razorpay request failed") from exc


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

async def create_plan(*, interval: str = "monthly", period: str = "monthly",
                      amount: int, currency: str = "INR", description: str = "") -> dict:
    """Create a Razorpay Plan.  amount is in paise (INR × 100)."""
    return await _post("/plans", {
        "period": period,
        "interval": 1,
        "item": {
            "name": description,
            "amount": amount,
            "currency": currency,
            "description": description,
        },
    })


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

async def create_subscription(
    *,
    plan_id: str,
    total_count: int = 12,
    customer_notify: int = 1,
    notes: dict | None = None,
) -> dict:
    """Create a Razorpay Subscription under a plan.

    total_count — number of billing cycles (e.g. 12 for a year of monthly billing).
    Trial is handled at the subscription level; pass start_at (Unix epoch) to delay
    the first charge beyond the free-trial window (set at the caller layer).
    """
    body: dict = {
        "plan_id": plan_id,
        "total_count": total_count,
        "customer_notify": customer_notify,
    }
    if notes:
        body["notes"] = notes
    return await _post("/subscriptions", body)


async def fetch_subscription(subscription_id: str) -> dict:
    """Fetch the latest state of a Razorpay Subscription."""
    return await _get(f"/subscriptions/{subscription_id}")


# ---------------------------------------------------------------------------
# Webhook signature verification — PURE function, unit-testable
# ---------------------------------------------------------------------------

def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Return True iff the HMAC-SHA256 of `body` using the webhook secret matches `signature`.

    Razorpay signs webhooks with HMAC-SHA256(payload_body, webhook_secret).
    The signature is sent in the X-Razorpay-Signature header as a hex digest.

    Returns False (not raises) so the caller can return a clean 400 without leaking details.
    If the webhook secret is not configured, always returns False.
    """
    secret = settings.razorpay_webhook_secret
    if not secret:
        return False
    expected = hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
