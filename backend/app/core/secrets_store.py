"""Fernet-based encrypt/decrypt for platform secrets stored in platform_settings.

The key is sourced from `settings.secrets_encryption_key` (base64-urlsafe, 32 bytes).
If the key is not configured, operations raise AppError(internal_error) — never
silently store plaintext secrets.

Generate a key once:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

import binascii

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.errors import AppError, ErrorCode


def _fernet() -> Fernet:
    key = settings.secrets_encryption_key
    if not key:
        raise AppError(ErrorCode.internal_error, "Secrets encryption key not configured")
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError, binascii.Error) as exc:
        raise AppError(ErrorCode.internal_error, "Invalid secrets encryption key") from exc


def encrypt(plaintext: str) -> str:
    """Return the Fernet-encrypted ciphertext as a UTF-8 string."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a Fernet token. Raises AppError(internal_error) on invalid token."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise AppError(ErrorCode.internal_error, "Failed to decrypt secret") from exc


def mask(token: str | None) -> str:
    """Return a safe masked representation — never returns the plaintext."""
    if not token:
        return ""
    return "**ENCRYPTED**"
