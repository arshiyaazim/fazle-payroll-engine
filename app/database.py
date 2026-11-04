"""
Fazle Payroll Engine — standalone database shim.

Provides asyncpg-backed helpers that mirror fazle-core's app.database surface:
    execute, fetch_all, fetch_one, fetch_val, db_conn, init_db, close_db

All SQL runs against the DATABASE_URL from app.config. Tables are created by
fazle_payroll_engine's own idempotent migrations (fpe_* prefix) at startup.
"""

from __future__ import annotations

import asyncpg
from contextlib import asynccontextmanager
from typing import Any, Optional

from app.config import get_settings

log = __import__("logging").getLogger("fazle.db")

_pool: Optional[asyncpg.Pool] = None


async def init_db() -> None:
    """Create the asyncpg connection pool. Call once at app startup."""
    global _pool
    settings = get_settings()
    _pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    log.info("[fpe.shim.db] pool ready")


async def close_db() -> None:
    """Close the asyncpg pool. Call once at app shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        log.info("[fpe.shim.db] pool closed")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_db() first")
    return _pool


@asynccontextmanager
async def db_conn():
    """Acquire a connection from the pool (or open a standalone connection)."""
    if _pool is not None:
        async with _pool.acquire() as conn:
            yield conn
        return
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)
    try:
        yield conn
    finally:
        await conn.close()


async def execute(sql: str, *args, conn: Optional[asyncpg.Connection] = None) -> str:
    if conn is not None:
        return await conn.execute(sql, *args)
    async with db_conn() as c:
        return await c.execute(sql, *args)


async def fetch_all(sql: str, *args, conn: Optional[asyncpg.Connection] = None) -> list[dict]:
    if conn is not None:
        rows = await conn.fetch(sql, *args)
        return [dict(r) for r in rows]
    async with db_conn() as c:
        rows = await c.fetch(sql, *args)
        return [dict(r) for r in rows]


async def fetch_one(sql: str, *args, conn: Optional[asyncpg.Connection] = None) -> Optional[dict]:
    if conn is not None:
        row = await conn.fetchrow(sql, *args)
        return dict(row) if row else None
    async with db_conn() as c:
        row = await c.fetchrow(sql, *args)
        return dict(row) if row else None


async def fetch_val(sql: str, *args, conn: Optional[asyncpg.Connection] = None) -> Any:
    if conn is not None:
        return await conn.fetchval(sql, *args)
    async with db_conn() as c:
        return await c.fetchval(sql, *args)
