"""Ledger cleanup: normalize vendors, unify currency, log every change.

The change log is the point of this workflow. An accountant will not trust a
tool that silently rewrites their data, so every alteration is recorded with
the original value, the new value, and the reason.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, replace

from iconomics.money import BGN_PER_EUR, Money
from iconomics.parsing import normalize_counterparty
from iconomics.workbook import Ledger, Problem, Row, Sheet

CLEAN_COLUMNS = [
    "Source Row",
    "Date",
    "Counterparty",
    "VAT Number",
    "Description",
    "Net",
    "VAT",
    "Currency",
    "Account",
]
CHANGE_COLUMNS = ["Source Row", "Field", "Before", "After", "Reason"]
EXCEPTION_COLUMNS = ["Source Row", "Field", "Raw Value", "Reason"]

#: Money columns get two forced decimals. Without this, Excel renders 410.00 as
#: "410", which reads as sloppy on a document an accountant hands to a client.
MONEY_FORMATS = {"Net": "0.00", "VAT": "0.00"}


@dataclass(frozen=True)
class Change:
    source_row: int
    field: str
    before: str
    after: str
    reason: str


@dataclass(frozen=True)
class CleanupResult:
    rows: list[Row]
    changes: list[Change]
    exceptions: list[Problem]


def canonical_vendor_map(rows: list[Row]) -> dict[str, str]:
    """Map each vendor spelling to the canonical spelling for its group.

    Grouping key is the normalized, case-folded name, so "Алфа ООД.",
    "алфа оод" and "Алфа  ООД" all land in one group. The canonical form is
    the most frequent original spelling, ties broken alphabetically so the
    result is deterministic across runs.
    """
    groups: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        key = normalize_counterparty(row.counterparty).casefold()
        groups[key][row.counterparty] += 1

    mapping: dict[str, str] = {}
    for variants in groups.values():
        best = min(variants.items(), key=lambda item: (-item[1], item[0]))[0]
        canonical = normalize_counterparty(best)
        for variant in variants:
            mapping[variant] = canonical
    return mapping


def _convert(money: Money, target: str) -> Money:
    return money.to_eur() if target == "EUR" else money.to_bgn()


def clean(ledger: Ledger, target_currency: str = "EUR") -> CleanupResult:
    """Normalize vendor names and restate every row into one currency."""
    if target_currency not in ("EUR", "BGN"):
        raise ValueError(f"unsupported target currency {target_currency!r}")

    vendors = canonical_vendor_map(ledger.rows)
    changes: list[Change] = []
    cleaned: list[Row] = []

    for row in ledger.rows:
        updates: dict[str, object] = {}

        canonical = vendors[row.counterparty]
        if canonical != row.counterparty:
            updates["counterparty"] = canonical
            changes.append(
                Change(
                    source_row=row.source_row,
                    field="counterparty",
                    before=row.counterparty,
                    after=canonical,
                    reason="merged vendor spelling variants",
                )
            )

        if row.currency != target_currency:
            reason = f"converted at the fixed rate 1 EUR = {BGN_PER_EUR} BGN"

            converted_net = _convert(row.amount_net, target_currency)
            updates["amount_net"] = converted_net
            updates["currency"] = target_currency
            changes.append(
                Change(
                    source_row=row.source_row,
                    field="amount_net",
                    before=str(row.amount_net),
                    after=str(converted_net),
                    reason=reason,
                )
            )

            if row.vat_amount is not None:
                converted_vat = _convert(row.vat_amount, target_currency)
                updates["vat_amount"] = converted_vat
                changes.append(
                    Change(
                        source_row=row.source_row,
                        field="vat_amount",
                        before=str(row.vat_amount),
                        after=str(converted_vat),
                        reason=reason,
                    )
                )

        cleaned.append(replace(row, **updates) if updates else row)

    cleaned.sort(key=lambda row: (row.date, row.source_row))
    changes.sort(key=lambda change: (change.source_row, change.field))
    return CleanupResult(rows=cleaned, changes=changes, exceptions=list(ledger.problems))


def to_sheets(result: CleanupResult) -> dict[str, Sheet]:
    """Render a cleanup result as the three contracted sheets.

    Dates are written as ISO strings rather than date-typed cells: openpyxl and
    exceljs disagree about date cell representation, and a string is
    unambiguous, sorts correctly, and compares cleanly across the two.
    """
    clean_rows = [
        [
            row.source_row,
            row.date.isoformat(),
            row.counterparty,
            row.vat_number or "",
            row.description,
            row.amount_net,
            row.vat_amount if row.vat_amount is not None else "",
            row.currency,
            row.account or "",
        ]
        for row in result.rows
    ]
    change_rows = [
        [c.source_row, c.field, c.before, c.after, c.reason] for c in result.changes
    ]
    exception_rows = [[p.source_row, p.field, p.raw, p.reason] for p in result.exceptions]

    return {
        "Clean": Sheet(
            columns=CLEAN_COLUMNS,
            rows=clean_rows,
            number_formats=MONEY_FORMATS,
        ),
        "Changes": Sheet(columns=CHANGE_COLUMNS, rows=change_rows),
        "Exceptions": Sheet(columns=EXCEPTION_COLUMNS, rows=exception_rows),
    }
