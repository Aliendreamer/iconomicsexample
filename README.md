# iconomics

A working accounting toolkit for Bulgarian books — built as a demonstration of what it is
like to do accounting work with [Claude Code](https://claude.com/claude-code).

It is meant to be read two ways at once. An accountant should see four tools that solve
real monthly jobs. Someone evaluating Claude Code should see how those tools were built,
and how a non-programmer drives them in plain language.

## The 2026 problem

Bulgaria adopted the euro on **1 January 2026** at the fixed irrevocable rate of
**€1 = 1.95583 BGN**. Every Bulgarian accountant is currently living with the consequences:

- 2025 books in BGN, 2026 books in EUR
- prior-year comparatives that must be restated
- January 2026 bank statements spanning the dual-circulation month, with both currencies
- exports from a dozen systems that each handle the changeover slightly differently

This is high-volume, error-prone, mechanical work. It is miserable by hand. It is exactly
what this toolkit is for.

## What it does

| Workflow | The job it replaces |
|---|---|
| **Ledger cleanup** | Untangling an ugly export: mixed date formats, numbers stored as text, duplicate vendors, mixed BGN/EUR rows |
| **Bank reconciliation** | Matching statement lines to ledger entries and chasing the ones that do not match |
| **VAT return** | Building the sales journal, purchase journal, declaration, and VIES list for the monthly filing |
| **Financial statements** | Rolling a trial balance into P&L, balance sheet, and cash flow with comparatives restated to EUR |

Every figure the toolkit produces carries a reference back to the source row it came from.
Nothing is silently dropped and nothing is silently guessed — anything ambiguous is put in
front of you for a decision.

## Status

**Ledger cleanup works, in both languages.** The other three workflows are designed
but not built. The full design is in
[`docs/superpowers/specs/2026-07-26-iconomics-design.md`](docs/superpowers/specs/2026-07-26-iconomics-design.md).

## Try it

```bash
uv venv --python 3.12 && uv pip install -e py/
npm --prefix js install

# Either of these — identical output
.venv/bin/python -m iconomics cleanup --in data/raw/ledger-2026-03.xlsx --out output/
node js/bin/iconomics.js cleanup --in data/raw/ledger-2026-03.xlsx --out output-js/

.venv/bin/python tools/check_parity.py    # prove the two agree, cell by cell
```

`data/raw/ledger-2026-03.xlsx` is the interesting one. It contains, deliberately:
three spellings of the same vendor, a credit note in accounting parentheses, a
correction entry still booked in BGN months after the changeover, the 9% reduced
rate next to a 0% intra-EU supply, a duplicated transaction, a row with no
counterparty, an Excel serial date among text dates, and an em dash where an
amount should be. Running it produces:

```
rows in: 14 · rows clean: 13 · changes: 4 · exceptions: 1
```

The one exception is the em dash — the toolkit declined to invent a number. The
four changes are two vendor merges and one BGN row restated, net and VAT. All of
it is written to a `Changes` sheet with the before value, the after value, and the
reason.

`ledger-2026-q1-large.xlsx` is 48 rows, for when reading the output by hand stops
being reasonable.

## Driving it from Claude

Three skills in `.claude/skills/` turn the CLI into something you talk to:

| Skill | Say something like |
|---|---|
| `ledger-cleanup` | "clean up the March ledger" |
| `euro-restatement` | "restate the 2025 figures in euro" |
| `exception-triage` | "why were those rows rejected?" |

The skills read `config/runtime.yaml` to decide whether to run the Python or the
JavaScript implementation, so they are written once and work for either.

## Design notes

- **Money is never a float.** `Decimal` in Python, a fixed-point representation in
  JavaScript. An accountant who sees `0.30000000000000004` in a VAT total never trusts the
  tool again.
- **Rules live in config, not code.** VAT rates and the chart of accounts are data files.
  When a rate changes, you edit YAML, not source.
- **The libraries stand alone.** Delete the Claude skills and the code still works and the
  tests still pass. Claude is the interface, not a load-bearing part of the arithmetic.
- **Two languages, one behaviour.** `tools/check_parity.py` runs both implementations
  over every sample file and diffs the output workbooks cell by cell, so they cannot
  drift apart silently. It has already caught one real bug: openpyxl and exceljs
  disagreed about whether an empty string is a blank cell.

## Not what this is

Not a commercial accounting package, and not tax advice. It computes; you decide what to
file. There is no direct submission to НАП — output is spreadsheets a human reviews.
