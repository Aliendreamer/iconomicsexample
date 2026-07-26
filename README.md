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

Design complete, implementation not yet started. The full design is in
[`docs/superpowers/specs/2026-07-26-iconomics-design.md`](docs/superpowers/specs/2026-07-26-iconomics-design.md).

Planned in two steps:

1. **The four workflows above** — Python and JavaScript implementations, sample data, skills
2. **SAF-T export** — Bulgaria's Standard Audit File for Tax, mandatory since January 2026

## Design notes

- **Money is never a float.** `Decimal` in Python, a fixed-point representation in
  JavaScript. An accountant who sees `0.30000000000000004` in a VAT total never trusts the
  tool again.
- **Rules live in config, not code.** VAT rates and the chart of accounts are data files.
  When a rate changes, you edit YAML, not source.
- **The libraries stand alone.** Delete the Claude skills and the code still works and the
  tests still pass. Claude is the interface, not a load-bearing part of the arithmetic.
- **Two languages, one behaviour.** Python and JavaScript implementations are verified
  against the same golden output files, so they cannot drift apart silently.

## Not what this is

Not a commercial accounting package, and not tax advice. It computes; you decide what to
file. There is no direct submission to НАП — output is spreadsheets a human reviews.
