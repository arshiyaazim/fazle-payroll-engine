"""
Fazle Payroll Engine — Background workers.

All workers are asyncio tasks (no Celery / RQ — consistent with existing fazle-core pattern).

Worker pipeline:
  1. message_processor_worker — polls fpe_message_processing_state for 'pending' rows,
       runs parser, calls AI enhancer if needed, stores parser_result.
  2. accounting_worker — polls for 'parsed' rows that are payment type,
       runs employee match, creates transactions, updates ledger.
  3. historical_sync_worker — calls historical_sync.historical_sync_loop() continuously.

Workers are started in FPE module __init__ via start_workers() and stopped on shutdown.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.database import fetch_all, fetch_one
from .accounting import create_transaction
from .ai_enhancer import ai_enhance_parse
from .employee import match_or_create_employee
from .gap_scan import gap_scan_loop
from .historical_sync import historical_sync_loop
from .ingestion import mark_processing_status, store_parser_result, store_unmatched
from .models import (
    IngestionRequest,
    MessageType,
    PayoutMethod,
    TxnCategory,
    TransactionCreateRequest,
)
from .normalizer import normalize_bd_phone
from .parser import parse_message

log = logging.getLogger("fazle.fpe.workers")

POLL_INTERVAL = 3       # seconds between DB polls
BATCH_SIZE = 20         # messages per worker tick
MAX_ATTEMPTS = 5        # give up after this many failures


# ── Worker management ─────────────────────────────────────────────────────────

_tasks: list[asyncio.Task] = []


async def start_workers(chat_jids: Optional[list[str]] = None) -> None:
    """Start all FPE background workers. Called from module __init__ on startup."""
    global _tasks
    _tasks = [
        asyncio.create_task(message_processor_worker(), name="fpe_msg_processor"),
        asyncio.create_task(accounting_worker(), name="fpe_accounting"),
        asyncio.create_task(historical_sync_loop(chat_jids), name="fpe_hsync"),
        asyncio.create_task(gap_scan_loop(chat_jids), name="fpe_gapscan"),
    ]
    log.info("[fpe.workers] started %d workers: %s", len(_tasks), [t.get_name() for t in _tasks])


async def stop_workers() -> None:
    """Cancel all FPE workers gracefully. Called on app shutdown."""
    global _tasks
    for task in _tasks:
        if not task.done():
            task.cancel()
    if _tasks:
        await asyncio.gather(*_tasks, return_exceptions=True)
    _tasks = []
    log.info("[fpe.workers] all workers stopped")


# ── Worker 1: Message processor (pending → parsing → parsed | skipped | failed) ──

async def message_processor_worker() -> None:
    """
    Poll fpe_message_processing_state for 'pending' rows.
    Run parser + optional AI enhancement on each message.
    """
    log.info("[fpe.worker.parser] started")
    while True:
        try:
            await _process_pending_batch()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.error("[fpe.worker.parser] error: %s", exc, exc_info=True)
        await asyncio.sleep(POLL_INTERVAL)


async def _process_pending_batch() -> None:
    rows = await fetch_all(
        """
        SELECT mps.id AS mps_id, mps.fpe_wa_message_id, mps.attempts,
               m.raw_content, m.is_from_me, m.timestamp_wa, m.source, m.chat_jid
        FROM fpe_message_processing_state mps
        JOIN fpe_wa_messages m ON m.id = mps.fpe_wa_message_id
        WHERE mps.status = 'pending'
          AND mps.attempts < $1
        ORDER BY mps.queued_at ASC
        LIMIT $2
        """,
        MAX_ATTEMPTS, BATCH_SIZE,
    )

    for row in rows:
        msg_id = row["fpe_wa_message_id"]
        content = row["raw_content"] or ""
        is_from_me = row["is_from_me"]

        try:
            await mark_processing_status(msg_id, "parsing")

            # Parse the message
            msg_date = row["timestamp_wa"].date() if row["timestamp_wa"] else None
            result = parse_message(content, msg_date)

            # AI enhancement if confidence low
            ai_enhanced = False
            ai_notes = None
            if result.confidence < 0.7 and content.strip():
                ai_data = await ai_enhance_parse(content, result.confidence)
                if ai_data and ai_data.get("is_payment"):
                    result = _ai_data_to_parse_result(ai_data, content, msg_date)
                    ai_enhanced = True
                    ai_notes = ai_data.get("notes")

            # Determine if we should skip (not from owner, or non-payment)
            if not is_from_me and result.message_type == MessageType.other:
                await store_unmatched(
                    msg_id, "accountant_other", content,
                    parser_confidence=result.confidence,
                )
                await mark_processing_status(msg_id, "skipped")
                continue

            # Store parser result
            parsed_data = {}
            if result.payment:
                p = result.payment
                parsed_data = {
                    "employee_id_phone": p.employee_id_phone,
                    "employee_name_raw": p.employee_name_raw,
                    "payout_phone": p.payout_phone,
                    "payout_method": p.payout_method.value if p.payout_method else None,
                    "amount": str(p.amount) if p.amount else None,
                    "txn_date": p.txn_date.isoformat() if p.txn_date else None,
                }
            elif result.balance_summary:
                bs = result.balance_summary
                parsed_data = {
                    "summary_date": bs.summary_date.isoformat() if bs.summary_date else None,
                    "total_due": str(bs.total_due) if bs.total_due else None,
                    "total_collected": str(bs.total_collected) if bs.total_collected else None,
                }

            await store_parser_result(
                msg_id,
                result.message_type.value,
                parsed_data,
                result.confidence,
                ai_enhanced,
                ai_notes,
            )

            # Transition to 'parsed' or 'skipped'
            if result.message_type == MessageType.payment:
                next_status = "parsed"
            else:
                next_status = "skipped"
                # Surface non-payment messages in the review queue so an admin
                # can inspect them (balance summaries, admin chitchat, etc.).
                if result.message_type.value == "balance_summary":
                    skip_reason = "balance_summary"
                elif is_from_me:
                    skip_reason = "admin_other"
                else:
                    skip_reason = "accountant_other"
                await store_unmatched(
                    msg_id, skip_reason, content,
                    detected_employee_name=parsed_data.get("employee_name_raw"),
                    detected_payout_phone=parsed_data.get("payout_phone"),
                    detected_payout_method=parsed_data.get("payout_method"),
                    parser_confidence=result.confidence,
                )
            await mark_processing_status(msg_id, next_status)

        except Exception as exc:
            log.error("[fpe.worker.parser] failed msg_id=%d: %s", msg_id, exc, exc_info=True)
            try:
                await store_unmatched(
                    msg_id, "parser_failed", content,
                )
            except Exception as ue:
                log.debug("[fpe.worker.parser] store_unmatched failed: %s", ue)
            await mark_processing_status(msg_id, "failed", str(exc)[:500])


# ── Worker 2: Accounting (parsed → accounting → done | failed) ───────────────

async def accounting_worker() -> None:
    """
    Poll for 'parsed' messages, run employee match, create transactions + ledger.
    """
    log.info("[fpe.worker.accounting] started")
    while True:
        try:
            await _process_parsed_batch()
            await _tick_zero_loss_gauges()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.error("[fpe.worker.accounting] error: %s", exc, exc_info=True)
        await asyncio.sleep(POLL_INTERVAL + 2)  # slight offset from parser


async def _tick_zero_loss_gauges() -> None:
    """Refresh Prometheus gauges for review queue + DLQ depth."""
    try:
        from app.database import fetch_val
        from modules import observability as obs
        pending_review = await fetch_val(
            "SELECT COUNT(*) FROM fpe_unmatched_messages WHERE review_status='pending'"
        ) or 0
        dlq = await fetch_val(
            "SELECT COUNT(*) FROM fpe_message_processing_state "
            "WHERE status='failed' AND attempts >= $1",
            MAX_ATTEMPTS,
        ) or 0
        obs.gauge("fpe_pending_review_count", float(pending_review))
        obs.gauge("fpe_dlq_count", float(dlq))
    except Exception as exc:
        log.debug("[fpe.gauges] tick failed: %s", exc)


async def _process_parsed_batch() -> None:
    rows = await fetch_all(
        """
        SELECT mps.fpe_wa_message_id,
               pr.message_type, pr.parsed_data, pr.confidence,
               m.raw_content, m.is_from_me, m.source
        FROM fpe_message_processing_state mps
        JOIN fpe_parser_results pr ON pr.fpe_wa_message_id = mps.fpe_wa_message_id
        JOIN fpe_wa_messages m ON m.id = mps.fpe_wa_message_id
        WHERE mps.status = 'parsed'
          AND pr.message_type = 'payment'
          AND m.is_from_me = TRUE
          AND mps.attempts < $1
        ORDER BY mps.queued_at ASC
        LIMIT $2
        """,
        MAX_ATTEMPTS, BATCH_SIZE,
    )

    for row in rows:
        msg_id = row["fpe_wa_message_id"]
        _raw_pdata = row["parsed_data"]
        import json as _json
        pdata = _json.loads(_raw_pdata) if isinstance(_raw_pdata, str) else (_raw_pdata or {})

        try:
            await mark_processing_status(msg_id, "accounting")

            name_raw = pdata.get("employee_name_raw")
            payout_phone = normalize_bd_phone(pdata.get("payout_phone"))
            id_phone = normalize_bd_phone(pdata.get("employee_id_phone"))
            amount_str = pdata.get("amount")
            method_str = pdata.get("payout_method") or "unknown"
            txn_date_str = pdata.get("txn_date")
            confidence = float(row["confidence"]) if row["confidence"] is not None else None

            if not amount_str:
                await store_unmatched(
                    msg_id, "no_amount_in_parse", row["raw_content"],
                    detected_payout_phone=payout_phone,
                    detected_employee_name=name_raw,
                    detected_payout_method=method_str,
                    parser_confidence=confidence,
                )
                await mark_processing_status(msg_id, "skipped")
                continue

            amount = Decimal(amount_str)
            if amount <= 0:
                await store_unmatched(
                    msg_id, "non_positive_amount", row["raw_content"],
                    detected_amount=amount,
                    detected_payout_phone=payout_phone,
                    detected_employee_name=name_raw,
                    detected_payout_method=method_str,
                    parser_confidence=confidence,
                )
                await mark_processing_status(msg_id, "skipped")
                continue

            txn_date = datetime.fromisoformat(txn_date_str).date() if txn_date_str else datetime.utcnow().date()

            # Employee matching / auto-create
            emp = await match_or_create_employee(name_raw, payout_phone, id_phone)

            if not emp:
                # IMPORTANT: amount detected but no employee. Money MUST remain
                # visible in the review queue. Do NOT insert into the immutable
                # ledger — that would corrupt accounting integrity.
                await store_unmatched(
                    msg_id, "no_employee_match", row["raw_content"],
                    detected_amount=amount,
                    detected_payout_phone=payout_phone,
                    detected_employee_name=name_raw,
                    detected_payout_method=method_str,
                    detected_txn_date=txn_date,
                    parser_confidence=confidence,
                )
                await mark_processing_status(msg_id, "failed", "employee match returned None")
                continue

            # Create transaction
            try:
                method = PayoutMethod(method_str) if method_str in PayoutMethod._value2member_map_ else PayoutMethod.unknown
            except (ValueError, KeyError):
                method = PayoutMethod.unknown

            req = TransactionCreateRequest(
                fpe_wa_message_id=msg_id,
                employee_id=emp.employee_id,
                employee_name_raw=name_raw,
                amount=amount,
                payout_phone=payout_phone,
                payout_method=method,
                txn_date=txn_date,
                txn_category=TxnCategory.salary,
                source_message_text=row["raw_content"],
            )
            txn = await create_transaction(req)

            await mark_processing_status(msg_id, "done")
            log.info(
                "[fpe.worker.acct] done msg=%d emp=%d txn=%s amount=%s",
                msg_id, emp.employee_id, txn.txn_ref[:12], amount,
            )

        except Exception as exc:
            log.error("[fpe.worker.acct] failed msg_id=%d: %s", msg_id, exc, exc_info=True)
            try:
                await store_unmatched(
                    msg_id, "accounting_failed", row["raw_content"],
                    detected_amount=Decimal(pdata.get("amount")) if pdata.get("amount") else None,
                    detected_payout_phone=normalize_bd_phone(pdata.get("payout_phone")),
                    detected_employee_name=pdata.get("employee_name_raw"),
                    detected_payout_method=pdata.get("payout_method"),
                    parser_confidence=float(row["confidence"]) if row["confidence"] is not None else None,
                )
            except Exception as ue:
                log.debug("[fpe.worker.acct] store_unmatched failed: %s", ue)
            await mark_processing_status(msg_id, "failed", str(exc)[:500])


# ── AI helpers ────────────────────────────────────────────────────────────────

def _ai_data_to_parse_result(ai_data: dict, content: str, msg_date):
    """Convert Ollama JSON response to a ParseResult."""
    from decimal import Decimal
    from .models import ParsedPayment, ParseResult, MessageType, PayoutMethod
    from .normalizer import normalize_bd_phone, normalize_payout_method

    raw_amount = ai_data.get("amount")
    amount = Decimal(str(raw_amount)) if raw_amount else None
    raw_phone = ai_data.get("payout_phone")
    phone = normalize_bd_phone(str(raw_phone)) if raw_phone else None
    raw_method = ai_data.get("payout_method") or "unknown"
    method_str = normalize_payout_method(raw_method)

    try:
        method = PayoutMethod(method_str)
    except ValueError:
        method = PayoutMethod.unknown

    confidence = float(ai_data.get("confidence", 0.7))

    if not amount:
        from .models import ParseResult, MessageType
        return ParseResult(message_type=MessageType.other, confidence=confidence)

    p = ParsedPayment(
        employee_name_raw=ai_data.get("employee_name"),
        payout_phone=phone,
        payout_method=method,
        amount=amount,
        txn_date=msg_date,
        confidence=confidence,
        raw_text=content,
    )
    return ParseResult(
        message_type=MessageType.payment,
        payment=p,
        confidence=confidence,
        ai_enhanced=True,
        ai_notes=ai_data.get("notes"),
    )
