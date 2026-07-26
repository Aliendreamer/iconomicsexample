from datetime import date, datetime
from decimal import Decimal

import pytest

from iconomics.parsing import (
    UnparseableAmount,
    UnparseableDate,
    from_excel_serial,
    normalize_counterparty,
    normalize_header,
    parse_amount,
    parse_date,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1234.56", "1234.56"),
        ("1234,56", "1234.56"),
        ("1 234,56", "1234.56"),  # space thousands, comma decimal
        ("1 234,56", "1234.56"),  # non-breaking space thousands
        ("1.234,56", "1234.56"),  # dot thousands, comma decimal
        ("1,234.56", "1234.56"),  # comma thousands, dot decimal
        ("1.234", "1234"),  # single dot, 3 digits => thousands
        ("12.50", "12.50"),  # single dot, 2 digits => decimal
        ("-123,45", "-123.45"),
        ("(123,45)", "-123.45"),  # accounting parentheses negative
        ("123,45 лв.", "123.45"),
        ("€123.45", "123.45"),
        ("  42  ", "42"),
        (1234.5, "1234.5"),  # numeric cell from openpyxl
        (Decimal("7.77"), "7.77"),
    ],
)
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == Decimal(expected)


@pytest.mark.parametrize("raw", ["", None, "n/a", "abc", "1,2,3", "1.2.3.4", True])
def test_parse_amount_rejects_garbage(raw):
    with pytest.raises(UnparseableAmount):
        parse_amount(raw)


def test_blank_amount_says_so_in_plain_words():
    with pytest.raises(UnparseableAmount, match="empty cell"):
        parse_amount(None)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("01.02.2026", date(2026, 2, 1)),  # Bulgarian dd.mm.yyyy
        ("1.2.2026", date(2026, 2, 1)),
        ("2026-02-01", date(2026, 2, 1)),
        ("01/02/2026", date(2026, 2, 1)),  # dd/mm/yyyy, consistent with dd.mm
        ("1-Feb-26", date(2026, 2, 1)),
        ("  2026-02-01  ", date(2026, 2, 1)),
        (datetime(2026, 2, 1, 13, 30), date(2026, 2, 1)),
        (date(2026, 2, 1), date(2026, 2, 1)),
        (46054, date(2026, 2, 1)),  # Excel serial
    ],
)
def test_parse_date(raw, expected):
    assert parse_date(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "not a date", "32.01.2026", "2026-13-01", True])
def test_parse_date_rejects_garbage(raw):
    with pytest.raises(UnparseableDate):
        parse_date(raw)


def test_blank_date_says_so_in_plain_words():
    with pytest.raises(UnparseableDate, match="empty cell"):
        parse_date(None)


def test_excel_serial_matches_the_openpyxl_epoch():
    assert from_excel_serial(46054) == date(2026, 2, 1)
    assert from_excel_serial(46023) == date(2026, 1, 1)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Дата", "дата"),
        ("  ДАТА:  ", "дата"),
        ("Сума  без   ДДС", "сума без ддс"),
        ("Date.", "date"),
    ],
)
def test_normalize_header(raw, expected):
    assert normalize_header(raw) == expected


def test_normalize_counterparty_preserves_case_but_collapses_noise():
    assert normalize_counterparty("  Алфа   ООД  ") == "Алфа ООД"
    assert normalize_counterparty("Алфа ООД.") == "Алфа ООД"


def test_normalize_counterparty_makes_whitespace_duplicates_identical():
    assert normalize_counterparty("Бета ЕООД ") == normalize_counterparty("Бета  ЕООД")
