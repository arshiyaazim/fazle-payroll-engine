# fazle-payroll-engine

Fazle Payroll Engine (FPE) — WhatsApp-based payroll processing module.

Parses incoming WhatsApp payment messages, matches employees, creates ledger
transactions, and provides a FastAPI router — all backed by PostgreSQL.

## Install from GitHub

```bash
pip install git+https://github.com/arshiyaazim/fazle-payroll-engine.git
```

To install a specific version/tag:
```bash
pip install git+https://github.com/arshiyaazim/fazle-payroll-engine.git@v1.0.0
```

To install into an existing venv (e.g. fazle-core):
```bash
cd /home/azim/core
source venv/bin/activate
pip install git+https://github.com/arshiyaazim/fazle-payroll-engine.git
```

## Usage within fazle-core

The module is designed to run inside **fazle-core**. It depends on:
- `app.database` — async PostgreSQL helpers (`execute`, `fetch_all`, `fetch_one`, `fetch_val`)
- `app.config` — settings (e.g. `INTERNAL_API_KEY`)

In `app/main.py` lifespan:
```python
from fazle_payroll_engine import start_fpe, stop_fpe
from fazle_payroll_engine.routes import router as fpe_router

app.include_router(fpe_router)

@asynccontextmanager
async def lifespan(app):
    await start_fpe()
    yield
    await stop_fpe()
```

## Update the installed package

```bash
pip install --upgrade git+https://github.com/arshiyaazim/fazle-payroll-engine.git
```

## Development (editable install)

```bash
git clone https://github.com/arshiyaazim/fazle-payroll-engine.git
cd fazle-payroll-engine
pip install -e .
```

## Migrations

SQL migrations are bundled inside the package and run automatically at startup via
`start_fpe()`. They are idempotent (`IF NOT EXISTS`).

## Module files

| File | Purpose |
|------|---------|
| `__init__.py` | `start_fpe()` / `stop_fpe()` lifecycle hooks |
| `routes.py` | FastAPI router — all `/api/fpe/` endpoints |
| `workers.py` | Asyncio background workers |
| `models.py` | Pydantic models & enums |
| `parser.py` | WhatsApp message parser |
| `ingestion.py` | Message ingestion pipeline |
| `accounting.py` | Transaction & ledger logic |
| `employee.py` | Employee matching & creation |
| `normalizer.py` | Phone / name normalization |
| `historical_sync.py` | Backfill historical messages |
| `gap_scan.py` | Gap detection scanner |
| `ai_enhancer.py` | AI-assisted parse enhancement |
| `checkpoint.py` | Sync checkpoint management |
| `reconcile.py` | Reconciliation helpers |
| `migrations/` | SQL schema migrations (001–005) |
