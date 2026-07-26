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

#: What shape of file to produce. Each of the five workflows needs one of these.
KINDS = ("ledger", "journal", "trial-balance", "bank")

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
    kind: str = "ledger"


class BadKind(ValueError):
    """Raised when an unknown kind of file is requested."""


# Shared value formulas. Extracted so a generated bank statement derives from the
# same numbers as the ledger for the same arguments — otherwise reconciling them
# would be meaningless.
def _net_cents(index: int) -> int:
    """Integer cents, wrapped. No floats, so both languages agree exactly."""
    return 7500 + (index * 21375) % 420000


def _vat_cents(net_cents: int, rate: int) -> int:
    return (net_cents * rate + 50) // 100


def _day_of(index: int, days_in_month: int) -> int:
    return index % days_in_month + 1


def _vendor_at(index: int):
    return VENDORS[index % len(VENDORS)]


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

        vendor, vat_number, account = _vendor_at(index)
        description = DESCRIPTIONS[index % len(DESCRIPTIONS)]
        rate = RATES[index % len(RATES)]
        day = _day_of(index, days_in_month)

        # Integer cents throughout: 7500 + a fixed stride, wrapped. No floats.
        net_cents = _net_cents(index)
        vat_cents = _vat_cents(net_cents, rate)

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


#: Counterparties used for the 0% rows in a journal, so an intra-EU supply and an
#: intra-EU acquisition both appear and the VIES list is non-empty.
EU_COUNTERPARTIES = (
    ("Nordwind GmbH", "DE811234567"),
    ("Zeta GmbH", "DE811234567"),
)

#: Accounts for a generated trial balance. Every code exists in config/coa.yaml, so
#: a generated file produces no unmapped accounts.
TRIAL_ACCOUNTS = (
    ("204", "Машини и оборудване", "debit"),
    ("302", "Материали", "debit"),
    ("411", "Клиенти", "debit"),
    ("501", "Каса", "debit"),
    ("503", "Разплащателна сметка", "debit"),
    ("4531", "ДДС покупки", "debit"),
    ("601", "Разходи за материали", "debit"),
    ("602", "Разходи за външни услуги", "debit"),
    ("604", "Разходи за заплати", "debit"),
    ("603", "Разходи за амортизации", "debit"),
    ("241", "Амортизация", "credit"),
    ("101", "Основен капитал", "credit"),
    ("401", "Доставчици", "credit"),
    ("421", "Персонал", "credit"),
    ("4532", "ДДС продажби", "credit"),
    ("452", "Данък върху печалбата", "credit"),
    ("701", "Приходи от продажби", "credit"),
    ("703", "Приходи от услуги", "credit"),
)

#: The plug account. Retained earnings is where a real trial balance absorbs the
#: difference, so it is the honest place to put it.
PLUG_ACCOUNT = ("122", "Неразпределена печалба")


def build_journal(spec: Spec) -> Sheet:
    """A sales-and-purchases journal for the VAT return.

    Adds a direction column and puts an EU counterparty on every 0% row, so both
    an intra-EU supply and an intra-EU acquisition appear and VIES is non-empty.
    """
    columns = [
        "Дата",
        "Вид документ",
        "Контрагент",
        "ДДС номер",
        "Описание",
        "Сметка",
        "Данъчна основа",
        "ДДС",
        "Ставка",
        "Валута",
    ]
    days_in_month = monthrange(spec.year, spec.month)[1]
    rows: list[list[object]] = []

    for index in range(spec.rows):
        vendor, vat_number, account = _vendor_at(index)
        rate = RATES[index % len(RATES)]
        # Deliberately period-5, not alternating: RATES has its 0% entry at
        # position 7, so a period-2 split would put every 0% row on the same side
        # and one of intra-EU supply / acquisition would never occur — leaving
        # VIES permanently empty. Periods 5 and 8 are coprime, so both appear.
        is_sale = index % 5 < 3

        # A 0% row only makes sense with a non-domestic counterparty; a 0% row to a
        # BG counterparty is the ambiguous zero-rated/exempt case the classifier
        # deliberately refuses to decide, so keep it out of generated data.
        if rate == 0:
            vendor, vat_number = EU_COUNTERPARTIES[index % len(EU_COUNTERPARTIES)]
            account = "701" if is_sale else "302"

        net_cents = _net_cents(index)
        vat_cents = _vat_cents(net_cents, rate)
        rows.append(
            [
                _format_date(spec.year, spec.month, _day_of(index, days_in_month),
                             spec.complexity, index),
                "Продажба" if is_sale else "Покупка",
                _vendor_spelling(vendor, spec.complexity, index),
                vat_number,
                DESCRIPTIONS[index % len(DESCRIPTIONS)],
                account,
                _format_amount(net_cents, spec.complexity),
                _format_amount(vat_cents, spec.complexity),
                str(rate),
                "EUR",
            ]
        )

    return Sheet(columns=columns, rows=rows)


def build_trial_balance(spec: Spec) -> Sheet:
    """A trial balance that balances, because `statements` refuses one that does not.

    Amounts are assigned deterministically and the difference is absorbed by
    retained earnings, which is where a real trial balance puts it.

    ``rows`` is capped at the account pool plus the plug: repeating an account code
    in a trial balance would not be a real trial balance.
    """
    usable = min(max(spec.rows - 1, 1), len(TRIAL_ACCOUNTS))
    rows: list[list[object]] = []
    debit_total = 0
    credit_total = 0

    for index in range(usable):
        code, name, side = TRIAL_ACCOUNTS[index]
        cents = 50000 + (index * 137500) % 4000000
        if side == "debit":
            debit_total += cents
            rows.append([code, name, _format_amount(cents, spec.complexity),
                         _format_amount(0, spec.complexity)])
        else:
            credit_total += cents
            rows.append([code, name, _format_amount(0, spec.complexity),
                         _format_amount(cents, spec.complexity)])

    difference = debit_total - credit_total
    plug_code, plug_name = PLUG_ACCOUNT
    if difference >= 0:
        rows.append([plug_code, plug_name, _format_amount(0, spec.complexity),
                     _format_amount(difference, spec.complexity)])
    else:
        # A debit balance on retained earnings is an accumulated loss. Valid.
        rows.append([plug_code, plug_name, _format_amount(-difference, spec.complexity),
                     _format_amount(0, spec.complexity)])

    return Sheet(
        columns=["Сметка", "Описание", "Дебит", "Кредит"], rows=rows
    )


def build_bank(spec: Spec) -> Sheet:
    """A bank statement corresponding to the ledger for the same arguments.

    This only has value if it *matches* — a random statement reconciles against
    nothing. So it derives from the same formulas as the ledger and then applies
    the distortions a real bank export has:

      * value dates lag by 0-3 days, so some matches drop to `probable`
      * narration is uppercased and truncated, the way bank feeds render it
      * roughly one row in seven never reaches the bank, leaving an unmatched
        ledger row to investigate
      * one bank charge is appended that the ledger never recorded

    Rows the ledger would have made unreadable (an em dash amount, a blank date)
    are skipped: they could not appear on a real statement.
    """
    days_in_month = monthrange(spec.year, spec.month)[1]
    rows: list[list[object]] = []

    for index in range(spec.rows):
        # Mirror the ledger's own skips and unreadable rows.
        if spec.complexity == "nasty" and index % 29 == 13:
            continue
        if spec.complexity == "nasty" and (index % 11 == 5 or index % 17 == 9):
            continue
        # Roughly one in seven payments has not cleared the bank.
        if index % 7 == 3:
            continue

        vendor, _vat_number, _account = _vendor_at(index)
        rate = RATES[index % len(RATES)]
        net_cents = _net_cents(index)
        if spec.complexity == "nasty" and index % 23 == 3:
            net_cents = -net_cents
        currency = "BGN" if spec.complexity != "clean" and index % 7 == 5 else "EUR"

        # Value dates lag sometimes, not usually. Lagging most rows would push
        # nearly everything to `probable` and bury the tier distinction that is
        # the point of the reconciliation.
        lag = (index % 3) + 1 if index % 4 == 1 else 0
        day = min(_day_of(index, days_in_month) + lag, days_in_month)

        narration = f"{vendor} {DESCRIPTIONS[index % len(DESCRIPTIONS)]}".upper()
        rows.append(
            [
                _format_date(spec.year, spec.month, day, spec.complexity, index),
                narration,
                _format_amount(net_cents, spec.complexity),
                currency,
            ]
        )

    # A charge the books never saw. This is the row a reconciliation exists to find.
    rows.append(
        [
            _format_date(spec.year, spec.month, days_in_month, spec.complexity, 0),
            "БАНКОВА ТАКСА ОБСЛУЖВАНЕ",
            _format_amount(1250, spec.complexity),
            "EUR",
        ]
    )

    return Sheet(columns=["Дата", "Основание", "Сума", "Валута"], rows=rows)


def build_for(spec: Spec) -> Sheet:
    """Dispatch on the requested kind."""
    if spec.kind not in KINDS:
        raise BadKind(
            f"unknown kind {spec.kind!r}; expected one of {', '.join(KINDS)}"
        )
    if spec.kind == "ledger":
        return build(spec)
    if spec.kind == "journal":
        return build_journal(spec)
    if spec.kind == "trial-balance":
        return build_trial_balance(spec)
    return build_bank(spec)


def describe(spec: Spec, sheet: Sheet) -> list[str]:
    """Summary lines for the CLI, so the user knows what they just got."""
    return [
        f"kind: {spec.kind}",
        f"rows: {len(sheet.rows)}",
        f"complexity: {spec.complexity}",
        f"period: {spec.year:04d}-{spec.month:02d}",
        f"columns: {len(sheet.columns)}",
    ]
