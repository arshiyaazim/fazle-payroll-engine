"""
Fazle Payroll Engine — standalone bridge shim.

Provides a minimal BridgeClient that mirrors fazle-core's app.bridge surface:
    BridgeClient.send(jid, text) -> bool
    BridgeClient.send_strict(jid, text) -> None
    get_bridge1() -> BridgeClient
    get_bridge2() -> BridgeClient

In standalone mode the bridges are best-effort: if the bridge HTTP endpoint is
unreachable, send() returns False and send_strict() raises BridgeSendError.
Workers log the failure and continue — payroll accounting never depends on
a successful WhatsApp reply.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import httpx

from app.config import get_settings

log = logging.getLogger("fazle.bridge")


class BridgeSendError(Exception):
    """Raised by BridgeClient.send_strict on any non-2xx or transport failure."""


class CircuitBreaker:
    """Per-bridge breaker. CLOSED -> OPEN after N failures in window."""

    def __init__(self, label: str, failure_threshold: int = 5,
                 window_seconds: int = 60, open_seconds: int = 60):
        self.label = label
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.open_seconds = open_seconds
        self._failures: list[float] = []
        self._opened_at: Optional[float] = None
        self._half_open_in_flight = False

    def state(self) -> str:
        if self._opened_at is None:
            return "closed"
        if time.time() - self._opened_at >= self.open_seconds:
            return "half_open"
        return "open"

    def allow(self) -> bool:
        st = self.state()
        if st == "closed":
            return True
        if st == "open":
            return False
        if self._half_open_in_flight:
            return False
        self._half_open_in_flight = True
        return True

    def record_success(self) -> None:
        self._failures.clear()
        self._opened_at = None
        self._half_open_in_flight = False

    def record_failure(self) -> None:
        now = time.time()
        self._failures = [t for t in self._failures if now - t < self.window_seconds]
        self._failures.append(now)


class BridgeClient:
    def __init__(self, base_url: str, label: str):
        self.base_url = base_url.rstrip("/")
        self.label = label
        timeout = float(os.getenv("OUTBOUND_BRIDGE_TIMEOUT_S", "10"))
        self._client = httpx.AsyncClient(timeout=timeout)
        self.breaker = CircuitBreaker(label)

    async def send(self, jid: str, text: str, *, authorization=None) -> bool:
        """Best-effort send. Returns True on success, False on failure."""
        try:
            await self.send_strict(jid, text, authorization=authorization)
            return True
        except BridgeSendError as exc:
            log.error("[%s] send error to %s: %s", self.label, jid, exc)
            return False

    async def send_strict(self, jid: str, text: str, *, authorization=None) -> None:
        """Strict send. Raises BridgeSendError on any failure."""
        if not self.breaker.allow():
            raise BridgeSendError("circuit breaker open")
        if not jid.endswith("@s.whatsapp.net") and not jid.endswith("@g.us"):
            jid = jid + "@s.whatsapp.net"
        try:
            r = await self._client.post(
                f"{self.base_url}/api/send",
                json={"recipient": jid, "message": text},
            )
            if r.status_code != 200:
                raise BridgeSendError(f"http {r.status_code}: {r.text[:200]}")
            self.breaker.record_success()
        except httpx.HTTPError as exc:
            self.breaker.record_failure()
            raise BridgeSendError(f"transport: {exc}") from exc

    async def close(self) -> None:
        await self._client.aclose()


# Singleton instances — lazily created
_bridge1: Optional[BridgeClient] = None
_bridge2: Optional[BridgeClient] = None


def get_bridge1() -> BridgeClient:
    global _bridge1
    if _bridge1 is None:
        settings = get_settings()
        _bridge1 = BridgeClient(settings.bridge1_url, "BR1")
    return _bridge1


def get_bridge2() -> BridgeClient:
    global _bridge2
    if _bridge2 is None:
        settings = get_settings()
        _bridge2 = BridgeClient(settings.bridge2_url, "BR2")
    return _bridge2
