"""Supabase Storage client — signed upload/download URLs via the service role.

Files go directly client <-> Storage through short-lived signed URLs; they never pass
through the serverless function. Bucket is private; type/size limits are enforced by the
bucket config (see 0011_storage_bucket.sql).
"""
from __future__ import annotations

import re
import uuid

import httpx

from app.core.config import settings
from app.core.errors import AppError, ErrorCode

BUCKET = "policy-documents"
ALLOWED_MIME = {"application/pdf", "image/png", "image/jpeg", "image/webp"}
MAX_SIZE_BYTES = 20 * 1024 * 1024


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
    }


def sanitize_filename(name: str) -> str:
    """Keep a safe basename — strip path separators and odd chars."""
    base = name.replace("\\", "/").split("/")[-1]
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    base = re.sub(r"_+", "_", base).strip("._") or "file"
    return base[:120]


def build_object_path(tenant_id, policy_id, file_name: str) -> str:
    return f"{tenant_id}/{policy_id}/{uuid.uuid4().hex}_{sanitize_filename(file_name)}"


async def create_signed_upload_url(path: str) -> str:
    if not (settings.supabase_url and settings.supabase_service_role_key):
        raise AppError(ErrorCode.internal_error, "Storage not configured")
    url = f"{settings.supabase_url}/storage/v1/object/upload/sign/{BUCKET}/{path}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=_headers())
    except httpx.HTTPError as exc:
        raise AppError(ErrorCode.upstream_error, "Storage unreachable") from exc
    if resp.status_code >= 400:
        raise AppError(ErrorCode.upstream_error, "Could not create upload URL")
    # {"url": "/object/upload/sign/<bucket>/<path>?token=..."}
    return f"{settings.supabase_url}/storage/v1{resp.json()['url']}"


async def create_signed_download_url(path: str, expires_in: int = 3600) -> str:
    url = f"{settings.supabase_url}/storage/v1/object/sign/{BUCKET}/{path}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=_headers(), json={"expiresIn": expires_in})
    except httpx.HTTPError as exc:
        raise AppError(ErrorCode.upstream_error, "Storage unreachable") from exc
    if resp.status_code >= 400:
        raise AppError(ErrorCode.upstream_error, "Could not create download URL")
    return f"{settings.supabase_url}/storage/v1{resp.json()['signedURL']}"


async def delete_object(path: str) -> None:
    url = f"{settings.supabase_url}/storage/v1/object/{BUCKET}/{path}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(url, headers=_headers())
    except httpx.HTTPError as exc:
        raise AppError(ErrorCode.upstream_error, "Storage unreachable") from exc
    if resp.status_code >= 400 and resp.status_code != 404:
        raise AppError(ErrorCode.upstream_error, "Could not delete file")
