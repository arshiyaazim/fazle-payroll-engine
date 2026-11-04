"""
Fazle Payroll Engine — standalone ollama shim.

Provides _ollama_sem (asyncio.Semaphore) that fazle_payroll_engine.ai_enhancer
imports from app.ollama. In standalone mode this semaphore serializes the few
Ollama enhancement calls the engine makes, preventing concurrent-request
timeout issues.

Created lazily on first access so importing this module does not require
DATABASE_URL to be set.
"""

from __future__ import annotations

import asyncio


_ollama_sem: asyncio.Semaphore | None = None


def get_ollama_sem() -> asyncio.Semaphore:
    """Return the shared Ollama semaphore, creating it on first use."""
    global _ollama_sem
    if _ollama_sem is None:
        _ollama_sem = asyncio.Semaphore(1)
    return _ollama_sem
