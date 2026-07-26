"""Command line entry point.

The subcommands, flags, exit codes, and stdout format here are a contract
shared with the JavaScript implementation. Changing any of them means
changing js/bin/iconomics.js in the same commit, or the parity test fails.

Exit codes:  0 success · 1 structural failure · 2 bad usage
"""

import argparse
import sys
from pathlib import Path

from iconomics.cleanup import clean, to_sheets
from iconomics.workbook import MissingColumn, load, write

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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
