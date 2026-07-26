"""Bank reconciliation: match statement lines against ledger entries.

Matching is tiered, and the tier is reported rather than hidden:

  exact     same amount, same date, and the counterparty appears in the
            statement narration
  probable  same amount within tolerance, date within a window, counterparty
            recognisable
  possible  amount matches, nothing else corroborates

Only ``exact`` is presented as settled. Everything else is a proposal for a human
to confirm, because a wrong match hides a real discrepancy — which is the exact
failure a reconciliation exists to catch.

Matching is greedy but deterministic: candidates are considered in date then row
order, and each ledger row and statement line is consumed at most once, so the
same inputs always produce the same pairing.
"""

from dataclasses import dataclass, replace
from decimal import Decimal

from iconomics.money import Money
from iconomics.parsing import normalize_counterparty
from iconomics.workbook import Ledger, Row, Sheet

EXACT = "exact"
PROBABLE = "probable"
POSSIBLE = "possible"

TIER_LABELS = {
    EXACT: "exact — amount, date and counterparty all agree",
    PROBABLE: "probable — amount agrees, date close, counterparty recognisable",
    POSSIBLE: "possible — amount agrees only",
}

MATCHED_COLUMNS = [
    "Tier",
    "Statement Row",
    "Statement Date",
    "Statement Narration",
    "Ledger Row",
    "Ledger Date",
    "Counterparty",
    "Amount",
    "Day Gap",
]
UNMATCHED_STATEMENT_COLUMNS = [
    "Statement Row",
    "Date",
    "Narration",
    "Amount",
    "Reason",
]
UNMATCHED_LEDGER_COLUMNS = ["Ledger Row", "Date", "Counterparty", "Amount", "Reason"]
SUMMARY_COLUMNS = ["Measure", "Count", "Value"]

MONEY_FORMATS = {"Amount": "0.00", "Value": "0.00"}

#: Default date window, in days, for a probable match. Bank value dates commonly
#: lag the invoice date by a few days.
DEFAULT_WINDOW = 5


@dataclass(frozen=True)
class Match:
    tier: str
    statement: Row
    ledger: Row
    day_gap: int


@dataclass(frozen=True)
class Reconciliation:
    matched: list[Match]
    unmatched_statement: list[Row]
    unmatched_ledger: list[Row]
    currency: str
    window: int
    restated: int = 0

    @property
    def confirmed(self) -> list[Match]:
        return [m for m in self.matched if m.tier == EXACT]

    @property
    def proposed(self) -> list[Match]:
        return [m for m in self.matched if m.tier != EXACT]


def _narration(row: Row) -> str:
    """A statement line's text: its description, or its counterparty column."""
    parts = [row.description or "", row.counterparty or ""]
    return " ".join(part for part in parts if part).strip()


def _counterparty_appears(ledger_row: Row, statement_row: Row) -> bool:
    """Whether the ledger counterparty is recognisable in the statement text."""
    name = normalize_counterparty(ledger_row.counterparty or "").casefold()
    if not name:
        return False
    haystack = normalize_counterparty(_narration(statement_row)).casefold()
    if not haystack:
        return False
    if name in haystack:
        return True
    # Fall back to the distinctive first word — bank narration often truncates
    # "Алфа ООД" to "АЛФА" or appends a reference.
    head = name.split(" ")[0]
    return len(head) >= 3 and head in haystack


def _tier(ledger_row: Row, statement_row: Row, window: int) -> tuple[str, int] | None:
    if ledger_row.amount_net != statement_row.amount_net:
        return None

    gap = abs((statement_row.date - ledger_row.date).days)
    named = _counterparty_appears(ledger_row, statement_row)

    if gap == 0 and named:
        return EXACT, gap
    if gap <= window and named:
        return PROBABLE, gap
    if gap <= window:
        return POSSIBLE, gap
    return None


def _restate(rows: list[Row], currency: str) -> tuple[list[Row], int]:
    """Put every row into one currency so amounts are comparable.

    Real March 2026 data still contains BGN correction entries, and an amount
    cannot be matched across currencies. Conversion is from the originally
    recorded amount at the fixed rate, and the count is reported so the run does
    not quietly change figures.
    """
    restated: list[Row] = []
    changed = 0
    for row in rows:
        if row.currency == currency:
            restated.append(row)
            continue
        convert = (lambda m: m.to_eur()) if currency == "EUR" else (lambda m: m.to_bgn())
        restated.append(
            replace(
                row,
                amount_net=convert(row.amount_net),
                vat_amount=convert(row.vat_amount) if row.vat_amount else None,
                currency=currency,
            )
        )
        changed += 1
    return restated, changed


def reconcile(
    statement: Ledger,
    ledger: Ledger,
    window: int = DEFAULT_WINDOW,
    currency: str = "EUR",
) -> Reconciliation:
    """Pair statement lines with ledger rows, best tier first."""
    statement_rows, restated_statement = _restate(statement.rows, currency)
    ledger_rows, restated_ledger = _restate(ledger.rows, currency)
    restated = restated_statement + restated_ledger

    statement_rows = sorted(statement_rows, key=lambda r: (r.date, r.source_row))
    ledger_rows = sorted(ledger_rows, key=lambda r: (r.date, r.source_row))

    used_ledger: set[int] = set()
    matched: list[Match] = []

    # Best tier first, so a clean pairing is never stolen by a weaker candidate.
    for tier in (EXACT, PROBABLE, POSSIBLE):
        for statement_row in statement_rows:
            if any(m.statement.source_row == statement_row.source_row for m in matched):
                continue
            for ledger_row in ledger_rows:
                if ledger_row.source_row in used_ledger:
                    continue
                verdict = _tier(ledger_row, statement_row, window)
                if verdict is None or verdict[0] != tier:
                    continue
                matched.append(
                    Match(
                        tier=tier,
                        statement=statement_row,
                        ledger=ledger_row,
                        day_gap=verdict[1],
                    )
                )
                used_ledger.add(ledger_row.source_row)
                break

    matched_statement_rows = {m.statement.source_row for m in matched}
    unmatched_statement = [
        row for row in statement_rows if row.source_row not in matched_statement_rows
    ]
    unmatched_ledger = [row for row in ledger_rows if row.source_row not in used_ledger]

    matched.sort(key=lambda m: (m.statement.date, m.statement.source_row))
    return Reconciliation(
        matched=matched,
        unmatched_statement=unmatched_statement,
        unmatched_ledger=unmatched_ledger,
        currency=currency,
        window=window,
        restated=restated,
    )


def _total(rows: list[Row], currency: str) -> Money:
    total = Money(Decimal("0.00"), currency)
    for row in rows:
        total = total + row.amount_net
    return total


def to_sheets(result: Reconciliation) -> dict[str, Sheet]:
    """Render the reconciliation. Confirmed and proposed are separate sheets."""

    def match_rows(matches: list[Match]) -> list[list[object]]:
        return [
            [
                m.tier,
                m.statement.source_row,
                m.statement.date.isoformat(),
                _narration(m.statement),
                m.ledger.source_row,
                m.ledger.date.isoformat(),
                m.ledger.counterparty,
                m.ledger.amount_net,
                m.day_gap,
            ]
            for m in matches
        ]

    confirmed = result.confirmed
    proposed = result.proposed

    summary_rows = [
        ["Statement lines matched (confirmed)", len(confirmed), _total([m.statement for m in confirmed], result.currency)],
        ["Statement lines proposed (review)", len(proposed), _total([m.statement for m in proposed], result.currency)],
        ["Statement lines unmatched", len(result.unmatched_statement), _total(result.unmatched_statement, result.currency)],
        ["Ledger rows unmatched", len(result.unmatched_ledger), _total(result.unmatched_ledger, result.currency)],
        ["Date window used (days)", result.window, ""],
        ["Rows restated to " + result.currency, result.restated, ""],
    ]

    return {
        "Matched": Sheet(
            columns=MATCHED_COLUMNS,
            rows=match_rows(confirmed),
            number_formats=MONEY_FORMATS,
        ),
        "Proposed": Sheet(
            columns=MATCHED_COLUMNS,
            rows=match_rows(proposed),
            number_formats=MONEY_FORMATS,
        ),
        "Unmatched Statement": Sheet(
            columns=UNMATCHED_STATEMENT_COLUMNS,
            rows=[
                [
                    row.source_row,
                    row.date.isoformat(),
                    _narration(row),
                    row.amount_net,
                    "no ledger entry with this amount in the date window",
                ]
                for row in result.unmatched_statement
            ],
            number_formats=MONEY_FORMATS,
        ),
        "Unmatched Ledger": Sheet(
            columns=UNMATCHED_LEDGER_COLUMNS,
            rows=[
                [
                    row.source_row,
                    row.date.isoformat(),
                    row.counterparty,
                    row.amount_net,
                    "not seen on the bank statement",
                ]
                for row in result.unmatched_ledger
            ],
            number_formats=MONEY_FORMATS,
        ),
        "Summary": Sheet(
            columns=SUMMARY_COLUMNS,
            rows=summary_rows,
            number_formats={"Value": "0.00"},
        ),
    }
