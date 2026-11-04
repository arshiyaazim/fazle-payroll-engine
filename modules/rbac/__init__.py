"""
Fazle Payroll Engine — standalone rbac shim.

Provides get_admin_by_api_key() that fazle_payroll_engine.routes imports.
In standalone mode this always returns None (no RBAC backend), so API-key auth
falls back to the internal_api_key check in settings. This is safe: the
require_api_key dependency first checks X-Internal-Key against
settings.internal_api_key, then tries rbac.get_admin_by_api_key() as fallback.
"""

from __future__ import annotations

from typing import Optional


async def get_admin_by_api_key(key: str) -> Optional[dict]:
    """Standalone stub — no RBAC backend configured. Returns None."""
    return None
