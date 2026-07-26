"""Parsers for the formats real accounting exports actually contain.

These are pure functions with no spreadsheet dependency, so every format
variant can be tested in isolation and a failure names the exact case.
"""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

_EXCEL_EPOCH = date(1899, 12, 30)
_CURRENCY_NOISE = re.compile(r"(лв\.?|BGN|EUR|€)", re.IGNORECASE)
_WHITESPACE = re.compile(r"[\s ]+")
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


class UnparseableAmount(ValueError):
    """Raised when a cell cannot be read as a monetary amount."""


class UnparseableDate(ValueError):
    """Raised when a cell cannot be read as a date."""


def from_excel_serial(serial: int | float) -> date:
    """Convert an Excel date serial number to a date."""
    return _EXCEL_EPOCH + timedelta(days=int(serial))


def _resolve_separators(text: str) -> str:
    """Normalize a numeric string to use '.' as the decimal separator.

    Bulgarian exports use comma as the decimal separator and space or dot for
    thousands; English-locale exports do the opposite. Resolution order:
      1. both separators present -> the rightmost is the decimal one
      2. one separator, 1-2 digits after -> decimal separator
      3. one separator, exactly 3 digits after -> thousands separator
      4. anything else -> unparseable
    """
    has_comma = "," in text
    has_dot = "." in text

    if has_comma and has_dot:
        if text.rfind(",") > text.rfind("."):
            return text.replace(".", "").replace(",", ".")
        return text.replace(",", "")

    if has_comma or has_dot:
        sep = "," if has_comma else "."
        if text.count(sep) > 1:
            raise UnparseableAmount(f"ambiguous separators in {text!r}")
        digits_after = len(text.rsplit(sep, 1)[1])
        if digits_after in (1, 2):
            return text.replace(sep, ".")
        if digits_after == 3:
            return text.replace(sep, "")
        raise UnparseableAmount(f"ambiguous separators in {text!r}")

    return text


def parse_amount(raw: object) -> Decimal:
    """Read a monetary amount from a spreadsheet cell of unknown format."""
    if raw is None:
        raise UnparseableAmount("empty cell")
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, bool):  # bool is an int subclass; never a valid amount
        raise UnparseableAmount("boolean is not an amount")
    if isinstance(raw, (int, float)):
        return Decimal(str(raw))
    if not isinstance(raw, str):
        raise UnparseableAmount(f"cannot read amount from {type(raw).__name__}")

    text = _CURRENCY_NOISE.sub("", raw).strip()
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    text = _WHITESPACE.sub("", text)
    if not text:
        raise UnparseableAmount("empty cell")

    text = _resolve_separators(text)
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise UnparseableAmount(f"cannot read amount from {raw!r}") from exc
    return -value if negative else value


def _parse_textual_date(text: str) -> date:
    # dd-Mon-yy / dd-Mon-yyyy
    match = re.fullmatch(r"(\d{1,2})[-\s]([A-Za-z]{3,})[-\s](\d{2,4})", text)
    if match:
        day, month_name, year = match.groups()
        month = _MONTHS.get(month_name[:3].lower())
        if month is None:
            raise UnparseableDate(f"unknown month in {text!r}")
        year_value = int(year)
        if year_value < 100:
            year_value += 2000
        return date(year_value, month, int(day))

    # ISO yyyy-mm-dd
    match = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return date(year, month, day)

    # Bulgarian dd.mm.yyyy and dd/mm/yyyy — day first
    match = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", text)
    if match:
        day, month, year = (int(part) for part in match.groups())
        if year < 100:
            year += 2000
        return date(year, month, day)

    raise UnparseableDate(f"cannot read date from {text!r}")


def parse_date(raw: object) -> date:
    """Read a date from a spreadsheet cell of unknown format.

    Ambiguous numeric dates are read day-first, matching Bulgarian convention.
    """
    if raw is None:
        raise UnparseableDate("empty cell")
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, bool):
        raise UnparseableDate("boolean is not a date")
    if isinstance(raw, (int, float)):
        try:
            return from_excel_serial(raw)
        except (ValueError, OverflowError) as exc:
            raise UnparseableDate(f"invalid Excel serial {raw!r}") from exc
    if not isinstance(raw, str):
        raise UnparseableDate(f"cannot read date from {type(raw).__name__}")

    text = raw.strip()
    if not text:
        raise UnparseableDate("empty cell")
    try:
        return _parse_textual_date(text)
    except UnparseableDate:
        raise
    except ValueError as exc:
        raise UnparseableDate(f"cannot read date from {raw!r}") from exc


def normalize_header(raw: str) -> str:
    """Canonicalize a column header for alias lookup."""
    text = _WHITESPACE.sub(" ", str(raw)).strip().rstrip(".:").strip()
    return text.lower()


def normalize_counterparty(raw: str) -> str:
    """Canonicalize a counterparty name so cosmetic variants collapse together."""
    return _WHITESPACE.sub(" ", str(raw)).strip().rstrip(".").strip()
