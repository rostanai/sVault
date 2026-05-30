"""Application configuration (pydantic-settings, 12-factor)."""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    app_name: str = "sVault API"
    env: Literal["dev", "staging", "prod"] = "dev"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Database — use the Supabase TRANSACTION POOLER (Supavisor) string on serverless,
    # never the direct connection. Format: postgresql+asyncpg://...:6543/postgres
    database_url: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""  # server-only; bypasses RLS
    supabase_jwt_secret: str = ""  # verifies Supabase-issued JWTs (HS256)
    jwt_algorithms: tuple[str, ...] = ("HS256",)

    # Timezone for all scheduling/expiry math (India default)
    timezone: str = "Asia/Kolkata"

    # Observability
    sentry_dsn: str = ""
    log_level: str = "INFO"

    # Alert engine — the scheduler (pg_cron/Vercel Cron) calls the dispatch endpoint
    # with this secret in the X-Cron-Secret header.
    cron_secret: str = ""
    # Channel credentials (empty = channel runs in "simulated" mode, logs intent only).
    whatsapp_token: str = ""
    sms_api_key: str = ""
    telegram_bot_token: str = ""
    email_api_key: str = ""

    # Razorpay (billing — M5). Empty = billing runs in "simulated" mode.
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # Secrets store — Fernet symmetric key (base64-urlsafe, 32 bytes).
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key())"
    secrets_encryption_key: str = ""

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
