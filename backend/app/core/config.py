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

    # Timezone for all scheduling/expiry math (India default)
    timezone: str = "Asia/Kolkata"

    # Observability
    sentry_dsn: str = ""
    log_level: str = "INFO"

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
