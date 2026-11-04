"""Fazle Payroll Engine — standalone host shim package.

Provides the `app.*` modules that fazle_payroll_engine imports from fazle-core,
so the payroll engine can run as a standalone FastAPI service without the full
fazle-core host application.

Shim modules:
  app.config        — pydantic-settings BaseSettings + get_settings()
  app.database      — asyncpg helpers (execute, fetch_all, fetch_one, fetch_val, db_conn)
  app.bridge        — BridgeClient + get_bridge1()/get_bridge2()
  app.ollama        — get_ollama_sem() semaphore accessor

Usage (standalone):
    import asyncio
    from app.database import init_db, close_db
    from fazle_payroll_engine import start_fpe, stop_fpe
    from fazle_payroll_engine.routes import router as fpe_router

    from fastapi import FastAPI
    app = FastAPI()

    app.include_router(fpe_router)

    @app.on_event("startup")
    async def _startup():
        await init_db()
        await start_fpe()

    @app.on_event("shutdown")
    async def _shutdown():
        await stop_fpe()
        await close_db()
"""
