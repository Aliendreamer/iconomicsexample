from datetime import date
from decimal import Decimal

from iconomics.cleanup import canonical_vendor_map, clean, to_sheets
from iconomics.money import Money
from iconomics.workbook import Ledger, Problem, Row


def row(source_row, counterparty, amount, currency="EUR", when=date(2026, 2, 1), vat=None):
    return Row(
        source_row=source_row,
        date=when,
        counterparty=counterparty,
        description="",
        amount_net=Money(Decimal(amount), currency),
        currency=currency,
        vat_amount=Money(Decimal(vat), currency) if vat is not None else None,
    )


def ledger_of(*rows, problems=()):
    return Ledger(
        rows=list(rows),
        problems=list(problems),
        unmapped_headers=[],
        source_path="x.xlsx",
    )


def test_vendor_variants_collapse_to_the_most_common_form():
    rows = [row(2, "Алфа ООД", "1"), row(3, "Алфа ООД", "1"), row(4, "алфа оод", "1")]
    mapping = canonical_vendor_map(rows)
    assert mapping["алфа оод"] == "Алфа ООД"
    assert mapping["Алфа ООД"] == "Алфа ООД"


def test_vendor_tie_is_broken_alphabetically_for_determinism():
    mapping = canonical_vendor_map([row(2, "Бета ЕООД", "1"), row(3, "бета еоод", "1")])
    assert mapping["Бета ЕООД"] == "Бета ЕООД"
    assert mapping["бета еоод"] == "Бета ЕООД"


def test_trailing_dot_variant_collapses():
    mapping = canonical_vendor_map([row(2, "Алфа ООД", "1"), row(3, "Алфа ООД.", "1")])
    assert mapping["Алфа ООД."] == "Алфа ООД"


def test_vendor_rename_is_logged_as_a_change():
    result = clean(ledger_of(row(2, "Алфа ООД", "1"), row(3, "алфа оод", "1")))
    renames = [c for c in result.changes if c.field == "counterparty"]
    assert len(renames) == 1
    assert renames[0].source_row == 3
    assert renames[0].before == "алфа оод"
    assert renames[0].after == "Алфа ООД"


def test_bgn_rows_are_converted_to_eur_and_logged():
    result = clean(ledger_of(row(2, "Алфа ООД", "195.583", currency="BGN")))
    assert result.rows[0].amount_net == Money(Decimal("100.00"), "EUR")
    assert result.rows[0].currency == "EUR"
    conversions = [c for c in result.changes if c.field == "amount_net"]
    assert conversions[0].before == "195.583 BGN"
    assert conversions[0].after == "100.00 EUR"
    assert "1.95583" in conversions[0].reason


def test_rows_already_in_target_currency_produce_no_change():
    assert clean(ledger_of(row(2, "Алфа ООД", "10.00", currency="EUR"))).changes == []


def test_vat_amount_is_converted_too():
    result = clean(
        ledger_of(
            row(2, "Алфа ООД", "195.583", currency="BGN", when=date(2025, 12, 1), vat="39.12")
        )
    )
    assert result.rows[0].vat_amount.currency == "EUR"
    assert any(c.field == "vat_amount" for c in result.changes)


def test_target_currency_can_be_bgn():
    result = clean(
        ledger_of(row(2, "Алфа ООД", "100.00", currency="EUR")), target_currency="BGN"
    )
    assert result.rows[0].amount_net == Money(Decimal("195.58"), "BGN")


def test_load_problems_pass_through_as_exceptions():
    problem = Problem(source_row=5, field="amount_net", raw="n/a", reason="empty cell")
    result = clean(ledger_of(row(2, "Алфа ООД", "1"), problems=[problem]))
    assert result.exceptions == [problem]


def test_sheets_have_the_contracted_names_and_headers():
    sheets = to_sheets(clean(ledger_of(row(2, "Алфа ООД", "1"))))
    assert list(sheets) == ["Clean", "Changes", "Exceptions"]
    assert sheets["Clean"].columns == [
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
    assert sheets["Changes"].columns == ["Source Row", "Field", "Before", "After", "Reason"]
    assert sheets["Exceptions"].columns == ["Source Row", "Field", "Raw Value", "Reason"]


def test_money_columns_carry_a_two_decimal_format():
    sheets = to_sheets(clean(ledger_of(row(2, "Алфа ООД", "1"))))
    assert sheets["Clean"].number_formats == {"Net": "0.00", "VAT": "0.00"}


def test_dates_are_written_as_iso_strings():
    sheets = to_sheets(clean(ledger_of(row(2, "Алфа ООД", "1", when=date(2026, 2, 1)))))
    assert sheets["Clean"].rows[0][1] == "2026-02-01"


def test_clean_rows_are_sorted_by_date_then_source_row():
    result = clean(
        ledger_of(
            row(4, "Алфа ООД", "1", when=date(2026, 2, 10)),
            row(2, "Алфа ООД", "1", when=date(2026, 2, 1)),
            row(3, "Алфа ООД", "1", when=date(2026, 2, 1)),
        )
    )
    assert [r.source_row for r in result.rows] == [2, 3, 4]
