"""Unit tests for fazle_payroll_engine.normalizer — pure functions, no fazle-core deps."""

import pytest

from fazle_payroll_engine.normalizer import (
    normalize_bd_phone,
    normalize_name,
    normalize_search_text,
    collapse_search_text,
    normalize_amount,
    normalize_payout_method,
    jid_to_phone,
)


# ── normalize_bd_phone ────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("01725494969", "01725494969"),          # already canonical
        ("+8801725494969", "01725494969"),        # +880 prefix
        ("8801725494969", "01725494969"),         # 880 prefix
        ("1725494969", "01725494969"),            # 10-digit (missing leading 0)
        ("০১৭২৫৪৯৪৯৬৯", "01725494969"),          # Bengali numerals
        ("+88 01725494969", "01725494969"),       # +88 prefix
        ("01725-494969", "01725494969"),          # with hyphen
        (" 01725494969 ", "01725494969"),         # surrounding whitespace
        (None, None),                              # None input
        ("", None),                                # empty string
        ("notaphone", None),                       # garbage
        ("0172549496", None),                      # too short (10 digits, doesn't start with... actually 10 digits starts with 0 -> prepend? no)
        ("018123456789", None),                    # 12 digits
        ("+8801812345678", "01812345678"),         # +880 + 10 digits = valid 11-digit
    ],
)
def test_normalize_bd_phone(raw, expected):
    assert normalize_bd_phone(raw) == expected


# ── normalize_name ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Jakir", "jakir"),
        ("  Md. Nasir  ", "md. nasir"),
        ("AL-MOMIN", "al-momin"),
        ("Debashish, S.G.", "debashish, s.g"),     # internal punctuation kept
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected


# ── normalize_search_text / collapse_search_text ──────────────────────────────

@pytest.mark.parametrize(
    "raw,search,collapsed",
    [
        ("Al-Momin", "al momin", "almomin"),
        ("  Al  Momin ", "al momin", "almomin"),
        ("Debashish, S.G.", "debashish s g", "debashishsg"),
        ("ALMOMIN", "almomin", "almomin"),
        ("Shohel Halisahar", "shohel halisahar", "shohelhalisahar"),
        ("", "", ""),
        (None, "", ""),
    ],
)
def test_normalize_search_and_collapse(raw, search, collapsed):
    assert normalize_search_text(raw) == search
    assert collapse_search_text(raw) == collapsed


# ── normalize_amount ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2200", 2200.0),
        ("2,200", 2200.0),
        ("১,৫৩০", 1530.0),          # Bengali digits
        ("75,468", 75468.0),
        ("150", 150.0),
        (None, None),
        ("", None),
        ("abc", None),
    ],
)
def test_normalize_amount(raw, expected):
    assert normalize_amount(raw) == expected


# ── normalize_payout_method ───────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("b", "bkash"),
        ("bkash", "bkash"),
        ("n", "nagad"),
        ("nagad", "nagad"),
        ("c", "cash"),
        ("cash", "cash"),
        ("r", "rocket"),
        ("rocket", "rocket"),
        ("bk", "bkash"),
        ("B", "bkash"),
        ("Nagad", "nagad"),
        ("unknown", "unknown"),
        ("", "unknown"),
        (None, "unknown"),
    ],
)
def test_normalize_payout_method(raw, expected):
    assert normalize_payout_method(raw) == expected


# ── jid_to_phone ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "jid,expected",
    [
        ("8801958122300@s.whatsapp.net", "01958122300"),
        ("01725494969@s.whatsapp.net", "01725494969"),
        ("101481722183752@lid", None),
        ("not-a-jid", None),
        ("", None),
    ],
)
def test_jid_to_phone(jid, expected):
    assert jid_to_phone(jid) == expected
