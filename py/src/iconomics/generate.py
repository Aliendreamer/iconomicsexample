"""Generate sample ledger exports at a requested size and messiness.

Two constraints shape this module:

  * **Deterministic.** No randomness anywhere. The same arguments produce a
    byte-identical file every time, so generated fixtures are stable and can be
    committed and diffed.
  * **Identical across languages.** js/src/generate.js must produce the same
    file from the same arguments. That is why every wrinkle is injected at a
    fixed row index and all money is computed in integer cents — a shared PRNG
    or any float arithmetic would drift between Python and JavaScript.
"""

from calendar import monthrange
from dataclasses import dataclass

from iconomics.workbook import Sheet

COMPLEXITIES = ("clean", "messy", "nasty")

# Pools are cycled by row index. Order matters: it is part of the contract with
# the JavaScript implementation.
VENDORS = (
    ("Алфа ООД", "BG123456789", "602"),
    ("Бета ЕООД", "BG987654321", "601"),
    ("Гама АД", "BG555444333", "601"),
    ("Делта ООД", "BG111222333", "602"),
    ("Епсилон ЕООД", "BG444555666", "602"),
    ("Йота ЕООД", "BG333222111", "602"),
    ("Хотел Родина АД", "BG777888999", "606"),
    ("Zeta GmbH", "DE811234567", "701"),
)

DESCRIPTIONS = (
    "Консултантски услуги",
    "Наем помещение",
    "Софтуерен абонамент",
    "Транспортни разходи",
    "Материали",
    "Поддръжка техника",
    "Нощувки командировка",
    "Интра-общностна доставка",
)

# VAT rate per row, cycled. 9% is accommodation, 0% is an intra-EU supply.
RATES = (20, 20, 20, 20, 20, 20, 9, 0)

_MONTHS_SHORT = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


class BadComplexity(ValueError):
    """Raised when an unknown complexity level is requested."""


@dataclass(frozen=True)
class Spec:
    rows: int
    complexity: str
    year: int
    month: int


def _headers(complexity: str) -> list[str]:
    """Header row. Each level spells things slightly differently on purpose."""
    if complexity == "clean":
        return [
            "Дата",
            "Контрагент",
            "ДДС номер",
            "Описание",
            "Сметка",
            "Сума без ДДС",
            "ДДС",
            "Ставка",
            "Валута",
        ]
    if complexity == "messy":
        return [
            "Дата",
            "Контрагент",
            "ДДС номер",
            "Описание",
            "Сметка",
            "Данъчна основа",
            "ДДС",
            "Ставка",
            "Валута",
        ]
    # nasty: the alternate counterparty spelling, plus a column the toolkit does
    # not know and must carry through rather than drop.
    return [
        "Дата",
        "Партньор",
        "ДДС номер",
        "Описание",
        "Сметка",
        "Данъчна основа",
        "ДДС",
        "Ставка",
        "Валута",
        "Вътрешен код",
    ]


def _group_thousands(digits: str) -> str:
    """Insert spaces every three digits from the right: 1234567 -> '1 234 567'."""
    parts = []
    while len(digits) > 3:
        parts.insert(0, digits[-3:])
        digits = digits[:-3]
    parts.insert(0, digits)
    return " ".join(parts)


def _format_amount(cents: int, complexity: str) -> str:
    """Render an amount the way the chosen level of export would write it."""
    negative = cents < 0
    magnitude = abs(cents)
    whole, fraction = divmod(magnitude, 100)

    if complexity == "clean":
        text = f"{whole}.{fraction:02d}"
        return f"-{text}" if negative else text

    text = f"{_group_thousands(str(whole))},{fraction:02d}"
    return f"({text})" if negative else text


def _excel_serial(year: int, month: int, day: int) -> int:
    """Days since the 1899-12-30 epoch openpyxl and exceljs both use."""
    from datetime import date

    return (date(year, month, day) - date(1899, 12, 30)).days


def _format_date(year: int, month: int, day: int, complexity: str, index: int) -> object:
    if complexity == "clean":
        return f"{year:04d}-{month:02d}-{day:02d}"
    if index % 9 == 4:
        # A date stored as a raw number, which is what Excel actually holds.
        return _excel_serial(year, month, day)
    if complexity == "nasty" and index % 13 == 6:
        return f"{day}-{_MONTHS_SHORT[month - 1]}-{year % 100:02d}"
    return f"{day:02d}.{month:02d}.{year:04d}"


def _vendor_spelling(name: str, complexity: str, index: int) -> str:
    """Introduce the cosmetic variants that make vendor merging necessary."""
    if complexity == "clean":
        return name
    if index % 5 == 2:
        return name.upper()
    if index % 5 == 3:
        return name.replace(" ", "  ") + "."
    return name


def build(spec: Spec) -> Sheet:
    """Build the sheet for a generation request."""
    if spec.complexity not in COMPLEXITIES:
        raise BadComplexity(
            f"unknown complexity {spec.complexity!r}; expected one of {', '.join(COMPLEXITIES)}"
        )
    if spec.rows < 1:
        raise ValueError("rows must be at least 1")

    headers = _headers(spec.complexity)
    days_in_month = monthrange(spec.year, spec.month)[1]
    rows: list[list[object]] = []

    for index in range(spec.rows):
        # A duplicated transaction: identical in every field to the row above.
        if spec.complexity == "nasty" and index % 29 == 13 and rows:
            rows.append(list(rows[-1]))
            continue

        vendor, vat_number, account = VENDORS[index % len(VENDORS)]
        description = DESCRIPTIONS[index % len(DESCRIPTIONS)]
        rate = RATES[index % len(RATES)]
        day = index % days_in_month + 1

        # Integer cents throughout: 7500 + a fixed stride, wrapped. No floats.
        net_cents = 7500 + (index * 21375) % 420000
        vat_cents = (net_cents * rate + 50) // 100

        # A credit note, written the way accountants write negatives.
        if spec.complexity == "nasty" and index % 23 == 3:
            net_cents = -net_cents
            vat_cents = -vat_cents

        # A tenth of rows in the messy levels are still booked in BGN — the
        # correction entries that keep appearing long after the changeover.
        currency = "BGN" if spec.complexity != "clean" and index % 7 == 5 else "EUR"

        date_cell = _format_date(spec.year, spec.month, day, spec.complexity, index)
        counterparty = _vendor_spelling(vendor, spec.complexity, index)
        net_cell = _format_amount(net_cents, spec.complexity)
        vat_cell = _format_amount(vat_cents, spec.complexity)

        if spec.complexity == "nasty":
            if index % 11 == 5:
                net_cell = "—"  # an em dash where a number belongs
            if index % 17 == 9:
                date_cell = ""
            if index % 19 == 7:
                counterparty = ""

        row: list[object] = [
            date_cell,
            counterparty,
            vat_number,
            description,
            account,
            net_cell,
            vat_cell,
            str(rate),
            currency,
        ]
        if spec.complexity == "nasty":
            row.append(f"INT-{index + 1:04d}")

        rows.append(row)

    return Sheet(columns=headers, rows=rows)


def describe(spec: Spec, sheet: Sheet) -> list[str]:
    """Summary lines for the CLI, so the user knows what they just got."""
    return [
        f"rows: {len(sheet.rows)}",
        f"complexity: {spec.complexity}",
        f"period: {spec.year:04d}-{spec.month:02d}",
        f"columns: {len(sheet.columns)}",
    ]
