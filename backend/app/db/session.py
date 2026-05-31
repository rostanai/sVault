"""Async SQLAlchemy engine + session dependency.

IMPORTANT (serverless): connect through the Supabase TRANSACTION POOLER (Supavisor,
port 6543). With pgbouncer transaction pooling + asyncpg you MUST disable the prepared-
statement cache and avoid SQLAlchemy pooling (NullPool) — otherwise you hit
"prepared statement already exists" under load.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

_engine = None
_SessionLocal: async_sessionmaker[AsyncSession] | None = None

if settings.database_url:
    _engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,  # pooling handled by Supavisor, not SQLAlchemy
        # NOTE: no pool_pre_ping — NullPool hands out a fresh connection every
        # request, so a pre-ping SELECT 1 only adds a round-trip with no benefit.
        connect_args={
            "statement_cache_size": 0,  # required behind pgbouncer (transaction pooling)
            "timeout": 10,  # fail fast if the pooler host is unreachable (no 45s hang)
            "command_timeout": 30,  # cap any single statement
        },
    )
    _SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async session (commit/rollback in the service)."""
    if _SessionLocal is None:
        raise RuntimeError("DATABASE_URL not configured")
    async with _SessionLocal() as session:
        yield session


def db_configured() -> bool:
    return _engine is not None


async def ping_db() -> None:
    """Open a connection and run `select 1` — used by the readiness check."""
    if _engine is None:
        raise RuntimeError("DATABASE_URL not configured")
    async with _engine.connect() as conn:
        await conn.exec_driver_sql("select 1")
