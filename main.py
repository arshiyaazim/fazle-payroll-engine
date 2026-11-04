"""
Fazle Payroll Engine — standalone FastAPI entry point.

Run:
    pip install -e .
    cp .env.example .env   # then edit .env with your DATABASE_URL and INTERNAL_API_KEY
    uvicorn main:app --host 0.0.0.0 --port 8200

Endpoints (all under /api/fpe/, auth via X-Internal-Key header):
  POST  /api/fpe/ingest
  GET   /api/fpe/transactions
  GET   /api/fpe/transactions/{id}
  POST  /api/fpe/transactions/{id}/reverse
  POST  /api/fpe/transactions/manual
  GET   /api/fpe/employees
  GET   /api/fpe/employees/{id}
  GET   /api/fpe/ledger/{emp_id}
  GET   /api/fpe/unmatched
  GET   /api/fpe/sync/status
  POST  /api/fpe/sync/trigger
  GET   /api/fpe/health
  ... (plus admin /admin/* and /normalization/* routes)
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI

from app.database import close_db, init_db
from fazle_payroll_engine import start_fpe, stop_fpe
from fazle_payroll_engine.routes import router as fpe_router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("fazle.fpe.standalone")

app = FastAPI(
    title="Fazle Payroll Engine",
    version="1.0.0",
    description="WhatsApp-based payroll processing module (standalone shim mode)",
)

app.include_router(fpe_router)


@app.on_event("startup")
async def _startup() -> None:
    log.info("[fpe.standalone] initializing database...")
    await init_db()
    log.info("[fpe.standalone] starting FPE workers...")
    await start_fpe()
    log.info("[fpe.standalone] startup complete")


@app.on_event("shutdown")
async def _shutdown() -> None:
    log.info("[fpe.standalone] stopping FPE workers...")
    await stop_fpe()
    log.info("[fpe.standalone] closing database...")
    await close_db()
    log.info("[fpe.standalone] shutdown complete")


@app.get("/health")
async def root_health():
    return {"status": "ok", "service": "fazle-payroll-engine"}
