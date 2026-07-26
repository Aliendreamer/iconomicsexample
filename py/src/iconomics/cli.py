"""Command line entry point.

The subcommands, flags, exit codes, and stdout format here are a contract
shared with the JavaScript implementation. Changing any of them means
changing js/bin/iconomics.js in the same commit, or the parity test fails.

Exit codes:  0 success · 1 structural failure · 2 bad usage
"""

import argparse
import sys
from pathlib import Path

from iconomics import reconcile as reconcile_module
from iconomics import statements as statements_module
from iconomics import vat as vat_module
from iconomics.cleanup import clean, to_sheets
from iconomics.coa import CoaError
from iconomics.generate import (
    COMPLEXITIES,
    KINDS,
    BadComplexity,
    BadKind,
    Spec,
    build_for,
    describe,
)
from iconomics.workbook import (
    STATEMENT_FIELDS,
    MissingColumn,
    load,
    load_trial_balance,
    write,
)

SUMMARY_KEYS = ("rows in", "rows clean", "changes", "exceptions", "output")
_LABEL_WIDTH = max(len(key) for key in SUMMARY_KEYS) + 2


def _summary_line(key: str, value: object) -> str:
    return f"  {key + ':':<{_LABEL_WIDTH}} {value}"


def _run_cleanup(args: argparse.Namespace) -> int:
    source = Path(args.input)
    try:
        ledger = load(source)
    except MissingColumn as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    result = clean(ledger, target_currency=args.currency)
    destination = Path(args.out) / f"{source.stem}-clean.xlsx"
    write(destination, to_sheets(result))

    rows_in = len(ledger.rows) + len(ledger.problems)
    print(f"cleanup: {source.name}")
    print(_summary_line("rows in", rows_in))
    print(_summary_line("rows clean", len(result.rows)))
    print(_summary_line("changes", len(result.changes)))
    print(_summary_line("exceptions", len(result.exceptions)))
    print(_summary_line("output", destination))
    return 0


def _parse_period(text: str) -> tuple[int, int]:
    parts = text.split("-")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"period must look like 2026-03, got {text!r}")
    try:
        year, month = int(parts[0]), int(parts[1])
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"period must look like 2026-03, got {text!r}"
        ) from None
    if not 1 <= month <= 12:
        raise argparse.ArgumentTypeError(f"month must be 1-12, got {month}")
    return year, month


def _run_generate(args: argparse.Namespace) -> int:
    year, month = args.period
    spec = Spec(
        rows=args.rows,
        complexity=args.complexity,
        year=year,
        month=month,
        kind=args.kind,
    )
    try:
        sheet = build_for(spec)
    except (BadComplexity, BadKind, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    destination = Path(args.out)
    write(destination, {"Ledger": sheet})

    print(f"generate: {destination.name}")
    for line in describe(spec, sheet):
        key, _, value = line.partition(": ")
        print(_summary_line(key, value))
    print(_summary_line("output", destination))
    return 0


def _run_vat_return(args: argparse.Namespace) -> int:
    source = Path(args.input)
    try:
        ledger = load(source)
        result = vat_module.build_return(ledger, currency=args.currency)
    except (MissingColumn, vat_module.VatConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    destination = Path(args.out) / f"{source.stem}-vat-return.xlsx"
    write(destination, vat_module.to_sheets(result))

    print(f"vat-return: {source.name}")
    print(_summary_line("sales rows", len(result.sales)))
    print(_summary_line("purchase rows", len(result.purchases)))
    print(_summary_line("vies rows", len(result.vies)))
    print(_summary_line("output vat", result.totals["vat_output"]))
    print(_summary_line("input vat", result.totals["vat_input"]))
    print(_summary_line("vat payable", result.totals["vat_net"]))
    print(_summary_line("unclassified", len(result.unclassified)))
    print(_summary_line("output", destination))
    return 0


def _run_statements(args: argparse.Namespace) -> int:
    source = Path(args.input)
    try:
        current = load_trial_balance(source, currency=args.currency)
        prior = None
        if args.prior:
            prior = load_trial_balance(
                Path(args.prior), currency=args.prior_currency or args.currency
            )
            if (args.prior_currency or args.currency) != args.currency:
                prior = statements_module.restate_trial_balance(prior, args.currency)
        result = statements_module.build(current, prior, currency=args.currency)
    except (MissingColumn, CoaError, statements_module.Unbalanced) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    destination = Path(args.out) / f"{source.stem}-statements.xlsx"
    write(destination, statements_module.to_sheets(result))

    print(f"statements: {source.name}")
    print(_summary_line("accounts", len(current.lines)))
    print(_summary_line("result", result.result))
    print(_summary_line("assets", result.assets))
    print(_summary_line("comparatives", "yes" if result.has_prior else "no"))
    print(_summary_line("unmapped", len(result.unmapped)))
    print(_summary_line("output", destination))
    return 0


def _run_reconcile(args: argparse.Namespace) -> int:
    bank_path = Path(args.bank)
    ledger_path = Path(args.ledger)
    try:
        statement = load(bank_path, required=STATEMENT_FIELDS)
        ledger = load(ledger_path)
    except MissingColumn as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    result = reconcile_module.reconcile(
        statement, ledger, window=args.window, currency=args.currency
    )
    destination = Path(args.out) / f"{bank_path.stem}-reconciliation.xlsx"
    write(destination, reconcile_module.to_sheets(result))

    print(f"reconcile: {bank_path.name} against {ledger_path.name}")
    print(_summary_line("confirmed", len(result.confirmed)))
    print(_summary_line("proposed", len(result.proposed)))
    print(_summary_line("bank unmatched", len(result.unmatched_statement)))
    print(_summary_line("ledger unmatched", len(result.unmatched_ledger)))
    print(_summary_line("output", destination))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="iconomics", description="Bulgarian accounting toolkit"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    cleanup = subparsers.add_parser("cleanup", help="normalize a messy ledger export")
    cleanup.add_argument("--in", dest="input", required=True, help="input .xlsx path")
    cleanup.add_argument("--out", required=True, help="output directory")
    cleanup.add_argument(
        "--currency",
        default="EUR",
        choices=("EUR", "BGN"),
        help="restate all amounts into this currency (default: EUR)",
    )
    cleanup.set_defaults(handler=_run_cleanup)

    generate = subparsers.add_parser(
        "generate", help="generate a sample ledger export at a chosen size and messiness"
    )
    generate.add_argument(
        "--rows", type=int, default=20, help="number of data rows (default: 20)"
    )
    generate.add_argument(
        "--complexity",
        default="messy",
        choices=COMPLEXITIES,
        help="clean = well-formed; messy = realistic Bulgarian export; "
        "nasty = adds unreadable values, blanks, credit notes and duplicates "
        "(default: messy)",
    )
    generate.add_argument(
        "--period",
        type=_parse_period,
        default=(2026, 3),
        metavar="YYYY-MM",
        help="month the rows are dated in (default: 2026-03)",
    )
    generate.add_argument(
        "--kind",
        default="ledger",
        choices=KINDS,
        help="what shape of file to produce: ledger (cleanup), journal "
        "(vat-return), trial-balance (statements), or bank (reconcile). "
        "A bank statement is generated to correspond to the ledger for the "
        "same arguments, so the two actually reconcile (default: ledger)",
    )
    generate.add_argument(
        "--out",
        required=True,
        help="output .xlsx file path (a file, unlike cleanup's --out directory)",
    )
    generate.set_defaults(handler=_run_generate)

    vat = subparsers.add_parser(
        "vat-return", help="build the VAT journals, declaration and VIES list"
    )
    vat.add_argument("--in", dest="input", required=True, help="ledger .xlsx path")
    vat.add_argument("--out", required=True, help="output directory")
    vat.add_argument("--currency", default="EUR", choices=("EUR", "BGN"))
    vat.set_defaults(handler=_run_vat_return)

    statements = subparsers.add_parser(
        "statements", help="roll a trial balance into P&L and balance sheet"
    )
    statements.add_argument(
        "--in", dest="input", required=True, help="trial balance .xlsx path"
    )
    statements.add_argument("--out", required=True, help="output directory")
    statements.add_argument(
        "--prior", help="prior period trial balance, for comparatives"
    )
    statements.add_argument("--currency", default="EUR", choices=("EUR", "BGN"))
    statements.add_argument(
        "--prior-currency",
        dest="prior_currency",
        choices=("EUR", "BGN"),
        help="currency the prior trial balance is recorded in; it is restated to "
        "--currency at the fixed rate (use BGN for a pre-2026 comparative)",
    )
    statements.set_defaults(handler=_run_statements)

    rec = subparsers.add_parser(
        "reconcile", help="match a bank statement against a ledger"
    )
    rec.add_argument("--bank", required=True, help="bank statement .xlsx path")
    rec.add_argument("--ledger", required=True, help="ledger .xlsx path")
    rec.add_argument("--out", required=True, help="output directory")
    rec.add_argument(
        "--window",
        type=int,
        default=reconcile_module.DEFAULT_WINDOW,
        help=f"days of tolerance between ledger and value date "
        f"(default: {reconcile_module.DEFAULT_WINDOW})",
    )
    rec.add_argument("--currency", default="EUR", choices=("EUR", "BGN"))
    rec.set_defaults(handler=_run_reconcile)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
