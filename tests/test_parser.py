"""Unit tests for fazle_payroll_engine.parser — pure regex, no fazle-core deps."""

from datetime import date

import pytest

from fazle_payroll_engine.parser import parse_message
from fazle_payroll_engine.models import MessageType


# ── Payment messages (documented patterns from wa_conversation export) ────────

def test_payment_id_prefix_single_line():
    """Pattern 1: \"ID: 01725494969 Jakir 01725494969(N) 2200/-\" """
    result = parse_message("ID: 01725494969 Jakir 01725494969(N) 2200/-")
    assert result.message_type == MessageType.payment
    p = result.payment
    assert p is not None
    assert p.employee_id_phone == "01725494969"
    assert p.payout_phone == "01725494969"
    assert p.payout_method.value == "nagad"
    assert p.amount == 2200
    assert p.employee_name_raw == "Jakir"
    assert result.confidence == 1.0


def test_payment_plus880_and_method():
    """Pattern 2: \"Md. Nasir SG - +8801318182022 ( B) = 200 /-\" """
    result = parse_message("Md. Nasir SG - +8801318182022 ( B) = 200 /-")
    assert result.message_type == MessageType.payment
    p = result.payment
    assert p is not None
    assert p.payout_phone == "01318182022"
    assert p.payout_method.value == "bkash"
    assert p.amount == 200
    assert p.employee_name_raw == "Md. Nasir SG"


def test_payment_no_method():
    """Pattern 3: \"Jolily MAX SG 01927317829(N) 510/-\" — has method anyway."""
    result = parse_message("Jolily MAX SG 01927317829(N) 510/-")
    assert result.message_type == MessageType.payment
    p = result.payment
    assert p is not None
    assert p.payout_phone == "01927317829"
    assert p.payout_method.value == "nagad"
    assert p.amount == 510


def test_payment_cash_method_parens():
    """Pattern 4: \"Saidul 01958122301(cash) 1530/-\" """
    result = parse_message("Saidul 01958122301(cash) 1530/-")
    assert result.message_type == MessageType.payment
    p = result.payment
    assert p is not None
    assert p.payout_phone == "01958122301"
    assert p.payout_method.value == "cash"
    assert p.amount == 1530


def test_payment_multiline_id_prefix():
    """Pattern 5: multi-line \"ID: ...\\nName- phone(B) amount/-\" """
    result = parse_message("ID: 01786178090\nAnis- 01786178090(B) 150/-")
    assert result.message_type == MessageType.payment
    p = result.payment
    assert p is not None
    assert p.employee_id_phone == "01786178090"
    assert p.payout_phone == "01786178090"
    assert p.payout_method.value == "bkash"
    assert p.amount == 150
    assert p.employee_name_raw == "Anis"


def test_payment_mainuddin():
    """Pattern 7: \"Mainuddin 01933689128(B) 1500/-\" """
    result = parse_message("Mainuddin 01933689128(B) 1500/-")
    assert result.message_type == MessageType.payment
    p = result.payment
    assert p is not None
    assert p.payout_phone == "01933689128"
    assert p.payout_method.value == "bkash"
    assert p.amount == 1500


def test_payment_amount_only_triggers_low_confidence():
    """Amount present but no phone/method/name → confidence 0.6 (AI would be called)."""
    result = parse_message("2200/-")
    assert result.message_type == MessageType.payment
    assert result.payment is not None
    assert result.payment.amount == 2200
    assert result.confidence == 0.6


# ── Balance summary (Bengali) ─────────────────────────────────────────────────

def test_balance_summary_bengali():
    """Pattern 6: \"31/3/26=টোটাল বাকি =75,468/-\" """
    result = parse_message("31/3/26=টোটাল বাকি =75,468/-")
    assert result.message_type == MessageType.balance_summary
    bs = result.balance_summary
    assert bs is not None
    assert bs.summary_date == date(2026, 3, 31)
    assert bs.total_due == 75468


# ── Cash / Income commands ────────────────────────────────────────────────────

def test_cash_command():
    result = parse_message("Cash 01725494969 Jakir 2200/-")
    assert result.message_type == MessageType.cash_command
    p = result.payment
    assert p is not None
    assert p.payout_phone == "01725494969"
    assert p.employee_id_phone == "01725494969"
    assert p.employee_name_raw == "Jakir"
    assert p.amount == 2200
    assert p.payout_method.value == "cash"
    assert result.confidence == 1.0


def test_cash_command_amount_no_slash():
    result = parse_message("Cash 01725494969 Jakir 5000")
    assert result.message_type == MessageType.cash_command
    assert result.payment.amount == 5000


def test_income_command():
    result = parse_message("Income 01725494969 Jakir 5000/-")
    assert result.message_type == MessageType.income_command
    p = result.payment
    assert p is not None
    assert p.amount == 5000
    assert p.payout_method.value == "cash"


def test_income_command_no_name():
    result = parse_message("Income 01725494969 5000/-")
    assert result.message_type == MessageType.income_command
    assert result.payment.amount == 5000


# ── Non-payment / edge cases ──────────────────────────────────────────────────

def test_empty_string():
    result = parse_message("")
    assert result.message_type == MessageType.other
    assert result.confidence == 1.0


def test_none_input():
    result = parse_message(None)
    assert result.message_type == MessageType.other


def test_non_payment_text():
    result = parse_message("সালাম, আপনি কেমন আছেন?")
    assert result.message_type == MessageType.other
