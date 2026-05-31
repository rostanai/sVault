"""Runtime secret resolution: platform_settings (DB) first, env var fallback.

The Super-Admin console writes secrets (AI key, Razorpay keys, channel keys) to
the `platform_settings` table. The runtime must READ them from there so changes
take effect without a redeploy — falling back to the process env (settings.*) when
a key isn't in the DB. Secret rows are Fernet-encrypted (decrypted here when the
encryption key is configured); non-secret rows are stored/returned as plaintext.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets_store
from app.core.errors import AppError
from app.db.models.billing import PlatformSetting

log = logging.getLogger("svault.secrets")


async def get_secret(db: AsyncSession, key: str, env_fallback: str = "") -> str:
    """Resolve a secret/config value.

    Order: platform_settings row (decrypted if secret) → env_fallback.
    Never raises on a missing/invalid DB row — always degrades to env_fallback.
    """
    try:
        row: PlatformSetting | None = (
            await db.execute(
                select(PlatformSetting).where(PlatformSetting.key == key)
            )
        ).scalar_one_or_none()
    except Exception as exc:  # pragma: no cover - DB hiccup must not break the feature
        log.warning("secret_lookup_failed key=%s: %s", key, exc)
        return env_fallback

    if row is None or not row.value_encrypted:
        return env_fallback

    if not row.is_secret:
        return row.value_encrypted

    # Secret row → attempt decrypt; if the encryption key is missing/invalid or the
    # stored value is plaintext (legacy/seeded), fall back gracefully.
    try:
        return secrets_store.decrypt(row.value_encrypted)
    except AppError:
        # Encryption key not configured, or value isn't valid ciphertext (e.g. it was
        # seeded as plaintext). Treat the stored value as-is rather than failing.
        return row.value_encrypted or env_fallback
