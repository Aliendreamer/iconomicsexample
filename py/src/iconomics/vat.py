"""Bulgarian VAT return: sales journal, purchase journal, declaration, VIES.

The declaration totals are *derived from* the journal rows rather than computed
alongside them. That is the whole design: two numbers computed independently can
disagree, and a return whose declaration does not tie to its journals will be
rejected. Here they cannot disagree, because there is only one computation.

Classification is data-driven — from the rate column and the counterparty's VAT
number prefix — never guessed from the description text. A row the rules do not
cover is flagged for a human rather than assigned a treatment.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import yaml

from iconomics.config import ConfigError, find_config_dir
from iconomics.money import Money, q2
from iconomics.workbook import Ledger, Problem, Row, Sheet

SALES_COLUMNS = [
    "Source Row",
    "Date",
    "Counterparty",
    "VAT Number",
    "Description",
    "Treatment",
    "Rate %",
    "Taxable Base",
    "VAT",
]
PURCHASE_COLUMNS = list(SALES_COLUMNS)
DECLARATION_COLUMNS = ["Line", "Description", "Amount"]
VIES_COLUMNS = ["Source Row", "Date", "Counterparty", "VAT Number", "Amount"]
RECONCILIATION_COLUMNS = ["Check", "From Journals", "From Declaration", "Agrees"]

MONEY_FORMATS = {"Taxable Base": "0.00", "VAT": "0.00", "Amount": "0.00"}

#: Treatment codes. Deliberately English and short — they are keys, not prose.
STANDARD = "standard"
REDUCED = "reduced"
INTRA_EU_SUPPLY = "intra_eu_supply"
INTRA_EU_ACQUISITION = "intra_eu_acquisition"
ZERO_DOMESTIC = "zero_domestic"

TREATMENT_LABELS = {
    STANDARD: "Облагаема доставка 20%",
    REDUCED: "Облагаема доставка 9%",
    INTRA_EU_SUPPLY: "Вътреобщностна доставка (0%)",
    INTRA_EU_ACQUISITION: "Вътреобщностно придобиване (обратно начисляване)",
    ZERO_DOMESTIC: "Нулева ставка / освободена — за проверка",
}


class VatConfigError(ConfigError):
    """Raised when config/vat-rates.yaml is missing or malformed."""


@dataclass(frozen=True)
class VatConfig:
    standard: Decimal
    reduced: Decimal
    zero: Decimal
    filing_day: int
    domestic_prefix: str
    declaration_cells: dict[str, str]

    @property
    def known_rates(self) -> tuple[Decimal, ...]:
        return (self.standard, self.reduced, self.zero)


def load_vat_config(config_dir: Path | None = None) -> VatConfig:
    directory = config_dir if config_dir is not None else find_config_dir()
    path = Path(directory) / "vat-rates.yaml"
    if not path.is_file():
        raise VatConfigError(f"missing config file: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rates = raw.get("rates") or {}
    for key in ("standard", "reduced", "zero"):
        if key not in rates:
            raise VatConfigError(f"{path}: rates.{key} is required")

    return VatConfig(
        standard=Decimal(str(rates["standard"])),
        reduced=Decimal(str(rates["reduced"])),
        zero=Decimal(str(rates["zero"])),
        filing_day=int(raw.get("filing_day", 14)),
        domestic_prefix=str(raw.get("domestic_prefix", "BG")).upper(),
        declaration_cells=dict(raw.get("declaration_cells") or {}),
    )


@dataclass(frozen=True)
class Classified:
    row: Row
    direction: str
    treatment: str
    rate: Decimal


@dataclass(frozen=True)
class VatReturn:
    sales: list[Classified]
    purchases: list[Classified]
    vies: list[Classified]
    unclassified: list[Problem]
    currency: str
    config: VatConfig
    totals: dict[str, Money] = field(default_factory=dict)


def infer_direction(row: Row) -> str | None:
    """Fall back to the account code when the ledger has no direction column.

    A 7xx account is revenue in the Bulgarian chart of accounts, so it is a sale;
    anything else is treated as a purchase. This is an inference, and rows that
    reach it are noted in the run summary rather than silently trusted.
    """
    if row.direction is not None:
        return row.direction
    if row.account and row.account.strip().startswith("7"):
        return "sale"
    if row.account:
        return "purchase"
    return None


def _is_domestic(vat_number: str | None, config: VatConfig) -> bool:
    if not vat_number:
        return True  # no VAT number at all: treat as domestic, not intra-EU
    return vat_number.strip().upper().startswith(config.domestic_prefix)


def classify(row: Row, direction: str, config: VatConfig) -> str | None:
    """Return a treatment code, or None if the rules do not cover this row."""
    if row.vat_rate is None:
        return None
    rate = row.vat_rate

    if rate == config.standard:
        return STANDARD
    if rate == config.reduced:
        return REDUCED
    if rate == config.zero:
        if _is_domestic(row.vat_number, config):
            # Zero-rated or exempt domestically. The distinction matters for the
            # return and cannot be read off the rate alone, so it goes to review.
            return ZERO_DOMESTIC
        return INTRA_EU_SUPPLY if direction == "sale" else INTRA_EU_ACQUISITION
    return None


def _sum(values: list[Money], currency: str) -> Money:
    total = Money(Decimal("0.00"), currency)
    for value in values:
        total = total + value
    return total


def build_return(ledger: Ledger, currency: str = "EUR") -> VatReturn:
    """Classify every row and derive the declaration from the journals."""
    config = load_vat_config()

    sales: list[Classified] = []
    purchases: list[Classified] = []
    vies: list[Classified] = []
    unclassified: list[Problem] = []

    for row in ledger.rows:
        direction = infer_direction(row)
        if direction is None:
            unclassified.append(
                Problem(
                    row.source_row,
                    "direction",
                    row.description or "(no description)",
                    "cannot tell whether this is a sale or a purchase; add a "
                    "direction column or an account code",
                )
            )
            continue

        treatment = classify(row, direction, config)
        if treatment is None:
            unclassified.append(
                Problem(
                    row.source_row,
                    "vat_rate",
                    "(blank)" if row.vat_rate is None else str(row.vat_rate),
                    "no VAT treatment matches this rate; expected one of "
                    + ", ".join(str(rate) for rate in config.known_rates),
                )
            )
            continue

        entry = Classified(
            row=row, direction=direction, treatment=treatment, rate=row.vat_rate
        )
        (sales if direction == "sale" else purchases).append(entry)
        if treatment == INTRA_EU_SUPPLY:
            vies.append(entry)

    def bases(entries, treatment):
        return [e.row.amount_net for e in entries if e.treatment == treatment]

    def taxes(entries, treatment):
        return [
            e.row.vat_amount
            for e in entries
            if e.treatment == treatment and e.row.vat_amount is not None
        ]

    totals = {
        "base_standard": _sum(bases(sales, STANDARD), currency),
        "vat_standard": _sum(taxes(sales, STANDARD), currency),
        "base_reduced": _sum(bases(sales, REDUCED), currency),
        "vat_reduced": _sum(taxes(sales, REDUCED), currency),
        "base_intra_eu_supply": _sum(bases(sales, INTRA_EU_SUPPLY), currency),
        "base_zero_domestic": _sum(bases(sales, ZERO_DOMESTIC), currency),
        "base_purchases": _sum(
            [e.row.amount_net for e in purchases], currency
        ),
        "vat_input": _sum(
            [e.row.vat_amount for e in purchases if e.row.vat_amount is not None],
            currency,
        ),
    }
    totals["vat_output"] = totals["vat_standard"] + totals["vat_reduced"]
    totals["vat_net"] = totals["vat_output"] - totals["vat_input"]

    return VatReturn(
        sales=sales,
        purchases=purchases,
        vies=vies,
        unclassified=unclassified,
        currency=currency,
        config=config,
        totals=totals,
    )


def _journal_rows(entries: list[Classified]) -> list[list[object]]:
    return [
        [
            e.row.source_row,
            e.row.date.isoformat(),
            e.row.counterparty,
            e.row.vat_number or "",
            e.row.description,
            TREATMENT_LABELS[e.treatment],
            e.rate,
            e.row.amount_net,
            e.row.vat_amount if e.row.vat_amount is not None else "",
        ]
        for e in sorted(entries, key=lambda e: (e.row.date, e.row.source_row))
    ]


#: Declaration lines, in filing order. Keys match config declaration_cells so an
#: official cell number can be attached without touching this code.
DECLARATION_LINES = (
    ("base_standard", "Данъчна основа на облагаеми доставки 20%"),
    ("vat_standard", "Начислен ДДС 20%"),
    ("base_reduced", "Данъчна основа на облагаеми доставки 9%"),
    ("vat_reduced", "Начислен ДДС 9%"),
    ("base_intra_eu_supply", "Данъчна основа на вътреобщностни доставки (0%)"),
    ("base_zero_domestic", "Данъчна основа, нулева ставка / освободена"),
    ("vat_output", "Общо начислен ДДС за периода"),
    ("base_purchases", "Данъчна основа на получени доставки"),
    ("vat_input", "ДДС с право на данъчен кредит"),
    ("vat_net", "ДДС за внасяне (+) / за възстановяване (-)"),
)


def to_sheets(result: VatReturn) -> dict[str, Sheet]:
    """Render the return as the sheets that make up a filing."""
    declaration_rows = [
        [result.config.declaration_cells.get(key, ""), label, result.totals[key]]
        for key, label in DECLARATION_LINES
    ]

    # The reconciliation proves the declaration was derived from the journals
    # rather than computed in parallel. If a line here ever disagreed, the return
    # would be rejected — so it is shown rather than assumed.
    journal_output = _sum(
        [e.row.vat_amount for e in result.sales if e.row.vat_amount is not None],
        result.currency,
    )
    journal_input = _sum(
        [e.row.vat_amount for e in result.purchases if e.row.vat_amount is not None],
        result.currency,
    )
    reconciliation_rows = [
        [
            "Начислен ДДС (sales journal vs declaration)",
            journal_output,
            result.totals["vat_output"],
            "yes" if journal_output == result.totals["vat_output"] else "NO",
        ],
        [
            "Данъчен кредит (purchase journal vs declaration)",
            journal_input,
            result.totals["vat_input"],
            "yes" if journal_input == result.totals["vat_input"] else "NO",
        ],
    ]

    vies_rows = [
        [
            e.row.source_row,
            e.row.date.isoformat(),
            e.row.counterparty,
            e.row.vat_number or "",
            e.row.amount_net,
        ]
        for e in sorted(result.vies, key=lambda e: (e.row.date, e.row.source_row))
    ]

    exception_rows = [
        [p.source_row, p.field, p.raw, p.reason] for p in result.unclassified
    ]

    return {
        "Дневник продажби": Sheet(
            columns=SALES_COLUMNS,
            rows=_journal_rows(result.sales),
            number_formats=MONEY_FORMATS,
        ),
        "Дневник покупки": Sheet(
            columns=PURCHASE_COLUMNS,
            rows=_journal_rows(result.purchases),
            number_formats=MONEY_FORMATS,
        ),
        "Декларация": Sheet(
            columns=DECLARATION_COLUMNS,
            rows=declaration_rows,
            number_formats=MONEY_FORMATS,
        ),
        "VIES": Sheet(
            columns=VIES_COLUMNS, rows=vies_rows, number_formats=MONEY_FORMATS
        ),
        "Reconciliation": Sheet(
            columns=RECONCILIATION_COLUMNS,
            rows=reconciliation_rows,
            number_formats={"From Journals": "0.00", "From Declaration": "0.00"},
        ),
        "Exceptions": Sheet(
            columns=["Source Row", "Field", "Raw Value", "Reason"], rows=exception_rows
        ),
    }
