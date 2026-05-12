"""
Fazle Payroll Engine — Deterministic regex payment message parser.

Design:
- Pure regex, zero network calls — runs in < 1 ms per message.
- AI enhancer (app.ollama) is invoked ONLY when confidence < 0.7.
- Patterns derived from actual owner→accountant conversation exports.

Observed message patterns (from wa_conversation_01880446111_01844836824.txt):
  1. "ID: 01725494969 Jakir 01725494969(N) 2200/-"
  2. "Md. Nasir SG - +8801318182022 ( B) = 200 /-"
  3. "Jolily MAX SG 01927317829(N) 510/-"
  4. "Saidul 01958122301(cash) 1530/-"
  5. "ID: 01786178090\\nAnis- 01786178090(B) 150/-"  (multi-line)
  6. "31/3/26=টোটাল বাকি =75,468/-"                 (balance summary)
  7. "Mainuddin 01933689128(B) 1500/-"

Confidence scoring:
  1.0 — all fields present (name + phone + method + amount)
  0.85 — amount + phone present, method missing
  0.75 — amount + name present, phone missing
  0.6  — amount only (triggers AI)
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Optional

from .models import MessageType, ParsedBalanceSummary, ParsedPayment, ParseResult, PayoutMethod
from .normalizer import normalize_amount, normalize_bd_phone, normalize_name, normalize_payout_method

# ── Regex building blocks ─────────────────────────────────────────────────────

# BD phone: +8801XXXXXXXXX | 8801XXXXXXXXX | 01XXXXXXXXX (9–13 digits with optional prefix)
_RE_PHONE = re.compile(
    r"(?:\+?880)?0[1-9]\d{9}",
    re.ASCII,
)

# Employee ID prefix line: "ID: 01XXXXXXXXX" or "ID: +8801XXXXXXXXX"
_RE_ID_PREFIX = re.compile(
    r"^[Ii][Dd]\s*[:：]\s*(\+?8{0,2}01\d+)",
    re.MULTILINE,
)

# Payment method in parentheses: (B), (N), (cash), ( B ), (bkash), (Nagad)
_RE_METHOD = re.compile(
    r"\(\s*([BbNnCcRr]|[Bb][Kk]|[Cc]ash|[Nn]agad|[Bb][Kk]ash|[Rr]ocket)\s*\)",
)

# Amount: digits/commas followed by /- or ৳
# Handles "2200/-", "2,200/-", "= 200 /-", "১,৫৩০/-"
_RE_AMOUNT = re.compile(
    r"[=\s]*([০-৯\d][০-৯\d,\.]*)\s*/[-–]",
)

# Balance summary patterns (Bengali):  "31/3/26=টোটাল বাকি =75,468/-"
_RE_BAL_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")
_RE_BAL_DUE  = re.compile(r"বাকি\s*[=:\s]+([০-৯\d][০-৯\d,]*)\s*/[-–]")
_RE_BAL_COLL = re.compile(r"জমা\s*[=:\s]+([০-৯\d][০-৯\d,]*)\s*/[-–]")

# Name heuristic: 1-5 Bengali/Latin words, may include dots and hyphens
# Appears BEFORE the phone number in the line
_RE_NAME_BEFORE_PHONE = re.compile(
    r"^([A-Za-z\u0980-\u09FF][A-Za-z\u0980-\u09FF\s\.\-]{1,50}?)"
    r"(?=\s*[\-–]?\s*(?:\+?8{0,2}01|\())",
)

_BENGALI_DIGITS_TRANS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

PARSER_VERSION = "v1"


# ── Public API ─────────────────────────────────────────────────────────────────

def parse_message(text: Optional[str], msg_date: Optional[date] = None) -> ParseResult:
    """
    Parse a single WhatsApp message text.
    Returns a ParseResult with .message_type set.
    """
    if not text or not text.strip():
        return ParseResult(message_type=MessageType.other, confidence=1.0)

    t = text.strip()

    # ── Balance summary detection (check first — short-circuits) ──────────────
    if _is_balance_summary(t):
        return _parse_balance_summary(t)

    # ── Payment detection ──────────────────────────────────────────────────────
    result = _parse_payment(t, msg_date)
    return result


# ── Internal helpers ──────────────────────────────────────────────────────────

def _is_balance_summary(text: str) -> bool:
    """Heuristic: contains Bengali accounting keywords."""
    return bool(
        re.search(r"টোটাল|বাকি|জমা", text)
        and _RE_AMOUNT.search(text)
    )


def _parse_balance_summary(text: str) -> ParseResult:
    bs = ParsedBalanceSummary(raw_text=text)

    m_date = _RE_BAL_DATE.search(text)
    if m_date:
        day, month, year = int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3))
        if year < 100:
            year += 2000
        try:
            bs.summary_date = date(year, month, day)
        except ValueError:
            pass

    m_due = _RE_BAL_DUE.search(text)
    if m_due:
        v = normalize_amount(m_due.group(1).translate(_BENGALI_DIGITS_TRANS))
        if v is not None:
            bs.total_due = Decimal(str(v))

    m_coll = _RE_BAL_COLL.search(text)
    if m_coll:
        v = normalize_amount(m_coll.group(1).translate(_BENGALI_DIGITS_TRANS))
        if v is not None:
            bs.total_collected = Decimal(str(v))

    return ParseResult(
        message_type=MessageType.balance_summary,
        balance_summary=bs,
        confidence=1.0,
    )


def _parse_payment(text: str, msg_date: Optional[date]) -> ParseResult:
    """
    Try to extract payment fields from message text.
    Returns ParseResult with message_type='payment' on success,
    or message_type='other' if no amount found at all.
    """
    # ── Amount (required) ──────────────────────────────────────────────────────
    t_ascii = text.translate(_BENGALI_DIGITS_TRANS)
    m_amt = _RE_AMOUNT.search(t_ascii)
    if not m_amt:
        return ParseResult(message_type=MessageType.other, confidence=1.0)

    raw_amount_str = m_amt.group(1)
    amount = normalize_amount(raw_amount_str)
    if amount is None or amount <= 0:
        return ParseResult(message_type=MessageType.other, confidence=1.0)

    p = ParsedPayment(
        raw_text=text,
        amount=Decimal(str(amount)),
        txn_date=msg_date,
    )
    confidence = 0.6  # baseline: amount only

    # ── Employee ID prefix ─────────────────────────────────────────────────────
    id_match = _RE_ID_PREFIX.search(text)
    if id_match:
        p.employee_id_phone = normalize_bd_phone(id_match.group(1))

    # ── Payout phone ──────────────────────────────────────────────────────────
    phones = _RE_PHONE.findall(t_ascii)
    # The payout phone is typically the last phone before the method tag or amount,
    # and is NOT the employee ID phone
    id_phone_digits = None
    if p.employee_id_phone:
        id_phone_digits = p.employee_id_phone[-10:]  # last 10 digits for comparison

    resolved_phones = [normalize_bd_phone(ph) for ph in phones]
    resolved_phones = [ph for ph in resolved_phones if ph is not None]

    # Prefer payout phone = phone that appears adjacent to method tag
    # If there is exactly one phone: that is the payout phone
    if len(resolved_phones) == 1:
        p.payout_phone = resolved_phones[0]
        confidence = max(confidence, 0.75)
    elif len(resolved_phones) >= 2:
        # Multiple phones: last one is typically the payout phone
        p.payout_phone = resolved_phones[-1]
        confidence = max(confidence, 0.75)

    # ── Payout method ─────────────────────────────────────────────────────────
    m_method = _RE_METHOD.search(text)
    if m_method:
        raw_method = m_method.group(1)
        p.payout_method = PayoutMethod(normalize_payout_method(raw_method))
        if p.payout_phone:
            confidence = max(confidence, 0.9)
        else:
            confidence = max(confidence, 0.75)
    else:
        p.payout_method = PayoutMethod.unknown

    # ── Employee name ─────────────────────────────────────────────────────────
    name = _extract_name(text, id_match)
    if name:
        p.employee_name_raw = name
        if p.payout_phone and p.payout_method != PayoutMethod.unknown:
            confidence = 1.0
        elif p.payout_phone:
            confidence = max(confidence, 0.85)
        else:
            confidence = max(confidence, 0.75)

    p.confidence = confidence

    return ParseResult(
        message_type=MessageType.payment,
        payment=p,
        confidence=confidence,
    )


def _is_valid_human_name(name: Optional[str]) -> bool:
    """Reject empty, pure-numeric, phone-like, or placeholder names."""
    if not name:
        return False
    s = name.strip()
    if len(s) < 2:
        return False
    if s.lower() in {"unknown", "unnamed", "none", "n/a", "na"}:
        return False
    # Pure digits / phone-shaped strings are not human names
    digits_only = re.sub(r"[\s\-\+\(\)\.]", "", s)
    if digits_only.isdigit():
        return False
    # Must contain at least one alphabetic char (Latin or Bengali)
    if not re.search(r"[A-Za-z\u0980-\u09FF]", s):
        return False
    return True


def _extract_name(text: str, id_match: Optional[re.Match]) -> Optional[str]:
    """
    Extract employee name from message.
    Strategy:
    1. If ID prefix present, STRIP it (don't drop the line) so single-line
       "ID: 019... Max Day 017...(B) 1070/-" still yields "Max Day".
    2. Try to find the name before the phone number.
    """
    lines = text.strip().splitlines()

    # Strip the ID-prefix span from whichever line contains it (if any),
    # but KEEP the rest of that line for name extraction.
    working_lines = []
    id_span_text = id_match.group(0) if id_match else None
    for l in lines:
        if id_span_text and id_span_text in l:
            l = l.replace(id_span_text, "", 1)
        working_lines.append(l)

    # Search each remaining line for name before phone
    for line in working_lines:
        line = line.strip()
        # Skip very short lines or lines that are just phones
        if not line or len(line) < 3:
            continue

        # Try name-before-phone pattern
        m = _RE_NAME_BEFORE_PHONE.match(line)
        if m:
            name = m.group(1).strip().rstrip("-– ")
            if _is_valid_human_name(name):
                return name

        # Fallback: if line has a phone, take everything before the phone
        phone_match = re.search(r"(?:\+?8{0,2}01\d{9})", line)
        if phone_match:
            candidate = line[:phone_match.start()].strip().rstrip("-– ")
            # Remove residual "ID: XXXXXXXXX" prefix if any
            candidate = re.sub(r"^[Ii][Dd]\s*[:：]\s*\S+\s*", "", candidate).strip()
            if _is_valid_human_name(candidate):
                return candidate

    return None
