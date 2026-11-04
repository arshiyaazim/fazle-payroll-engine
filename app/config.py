"""
Fazle Payroll Engine — standalone config shim.

Mirrors fazle-core's app.config.Settings surface that fazle_payroll_engine
reads, but reads from this repo's own `.env` (or environment variables) so the
engine can run without fazle-core.

Required environment variables:
    DATABASE_URL      PostgreSQL connection string (asyncpg-compatible)
    INTERNAL_API_KEY  API key for X-Internal-Key auth on /api/fpe/* endpoints

Optional environment variables (with sensible defaults):
    OLLAMA_URL            http://localhost:11434
    OLLAMA_MODEL          hermes3:3b
    BRIDGE1_URL           http://localhost:8082
    BRIDGE2_URL           http://localhost:8081
    FPE_CASH_AUTHORIZED_PHONES   (comma-separated)
    FPE_INCOME_AUTHORIZED_PHONES (comma-separated)
    FPE_SYNC_CHAT_JIDS    (comma-separated target JIDs for historical sync)
    ACCOUNTANT_PHONE      default accountant phone for sync target JID
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ──
    database_url: str

    # ── Auth ──
    internal_api_key: str = ""

    # ── Ollama ──
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "hermes3:3b"

    # ── WhatsApp bridges ──
    bridge1_url: str = "http://localhost:8082"
    bridge2_url: str = "http://localhost:8081"

    # ── FPE payroll settings ──
    fpe_cash_authorized_phones: str = ""
    fpe_income_authorized_phones: str = ""
    fpe_sync_chat_jids: str = ""
    accountant_phone: str = ""

    # ── App ──
    app_port: int = 8200
    log_level: str = "INFO"
    debug: bool = False

    # ── Convenience properties (mirror fazle-core) ──
    @property
    def fpe_cash_authorized_phone_list(self) -> list[str]:
        return [n.strip() for n in self.fpe_cash_authorized_phones.split(",") if n.strip()]

    @property
    def fpe_income_authorized_phone_list(self) -> list[str]:
        return [n.strip() for n in self.fpe_income_authorized_phones.split(",") if n.strip()]

    @field_validator("debug", mode="before")
    @classmethod
    def _parse_debug(cls, v):
        if isinstance(v, str) and v.strip().lower() in {"release", "prod", "production"}:
            return False
        return v

    model_config = {
        "env_file": str(Path(__file__).resolve().parents[1] / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
