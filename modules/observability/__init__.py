"""
Fazle Payroll Engine — standalone observability shim.

Provides inc() and gauge() that fazle_payroll_engine.workers imports
(_tick_zero_loss_gauges). In standalone mode these are no-ops that keep the
module importable and functional without a Prometheus backend.
"""

from __future__ import annotations

from typing import Optional


def inc(name: str, value: float = 1.0, labels: Optional[dict] = None) -> None:
    """No-op counter increment (standalone shim)."""
    return None


def gauge(name: str, value: float, labels: Optional[dict] = None) -> None:
    """No-op gauge set (standalone shim)."""
    return None
