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

| Workflow | The job it replaces | Python | JS |
|---|---|---|---|
| **Ledger cleanup** | Untangling an ugly export: mixed date formats, numbers stored as text, duplicate vendors, mixed BGN/EUR rows | yes | yes |
| **Bank reconciliation** | Matching statement lines to ledger entries and chasing the ones that do not match | yes | yes |
| **VAT return** | Building the sales journal, purchase journal, declaration, and VIES list for the monthly filing | yes | yes |
| **Financial statements** | Rolling a trial balance into P&L and balance sheet, comparatives restated to EUR | yes | yes |

All four workflows exist in both languages, and `tools/check_parity.py` diffs every
one of the five subcommands cell by cell.

Every figure the toolkit produces carries a reference back to the source row it came from.
Nothing is silently dropped and nothing is silently guessed — anything ambiguous is put in
front of you for a decision.

## Status

**All four workflows work, in both languages.** The full design is in
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

Nine skills in `.claude/skills/` turn the CLI into something you talk to:

| Skill | Say something like |
|---|---|
| `ledger-workflow` | "process all of these, take it from here" |
| `generate-ledger` | "make me a test file with 100 rows" |
| `ledger-cleanup` | "clean up the March ledger" |
| `euro-restatement` | "restate the 2025 figures in euro" |
| `exception-triage` | "why were those rows rejected?" |
| `bank-reconciliation` | "reconcile the March bank statement" |
| `bg-vat-return` | "prepare the VAT return for March" |
| `financial-statements` | "produce the P&L and balance sheet" |
| `explain-toolkit` | "why does it say 1234 when my file says 1.234?" |

The skills read `config/runtime.yaml` to decide whether to run the Python or the
JavaScript implementation, so they are written once and work for either.

### The workflow skill

`ledger-workflow` runs the other four as one sequence — pick files, clean them,
verify the restatement, then triage every exception across all of them together.
It asks which files and which target currency, then hands back a single table:

| File | Rows in | Clean | Changes | Exceptions |
|---|---|---|---|---|
| ledger-2025-12.xlsx | 4 | 4 | 8 | 0 |
| ledger-2026-01.xlsx | 5 | 5 | 4 | 0 |
| ledger-2026-02.xlsx | 6 | 4 | 1 | 2 |
| ledger-2026-03.xlsx | 14 | 13 | 4 | 1 |
| ledger-2026-q1-large.xlsx | 48 | 48 | 10 | 0 |
| **Total** | **77** | **74** | **27** | **3** |

Those are the real numbers from the committed sample data. A malformed file does
not abort the run — it is reported at the end and the other files still process.

The report leads with the three rows that need a human decision, because that is
the only part of the output carrying an obligation.

### The explainer skill

`explain-toolkit` answers questions about the toolkit and the accounting rules
behind it. Its central discipline is classifying the question before answering,
because each kind has a different standard of proof:

| Kind | Answered from |
|---|---|
| What the code does | Running it and quoting real output |
| Why it was built this way | The design record — reasoning that isn't derivable from the code |
| What the law requires | A citable source. Never memory |
| What a skill can do for you | Its `SKILL.md`, including a plain "no" when that's the answer |

So "does it round 0.025 up?" gets demonstrated, "why not floats?" gets the
reasoning, and "when is the VAT return due?" gets searched and cited — even though
a date is written in `CLAUDE.md`, because regulations drift and those notes carry a
research date of 2026-07-26.

`generate-ledger` asks three questions — which kind of file, how many rows, and how
messy — then builds it:

```bash
.venv/bin/python -m iconomics generate --kind ledger        --rows 100 --out /tmp/ledger.xlsx
.venv/bin/python -m iconomics generate --kind journal       --rows 100 --out /tmp/journal.xlsx
.venv/bin/python -m iconomics generate --kind trial-balance --rows 100 --out /tmp/tb.xlsx
.venv/bin/python -m iconomics generate --kind bank          --rows 100 --out /tmp/bank.xlsx
```

There is a kind for every workflow, so you can practise on any of them without
having real books to hand:

| `--kind` | Feeds | Note |
|---|---|---|
| `ledger` | `cleanup` | The default |
| `journal` | `vat-return` | Adds direction and 0% EU rows, so VIES is non-empty |
| `trial-balance` | `statements` | **Always balances** — retained earnings absorbs the difference |
| `bank` | `reconcile` | **Derived from the ledger** for the same arguments, then distorted the way a bank export is |

The bank statement is the interesting one: a random statement reconciles against
nothing, so it is generated from the same formulas as the ledger and then given
lagged value dates, uppercased narration, roughly one payment in seven not yet
cleared, and one bank charge the ledger never saw. Generate both with identical
arguments and they reconcile the way real books do.

| Complexity | Contains |
|---|---|
| `clean` | ISO dates, dot decimals, one spelling per vendor, all EUR — zero exceptions |
| `messy` | Bulgarian dates, comma decimals, vendor variants, some BGN rows, Excel serial dates |
| `nasty` | All of the above plus unreadable amounts, blank dates and counterparties, credit notes, duplicates, and an unrecognized column |

Generation is deterministic — no randomness — so the same arguments always produce
the same file, and generated fixtures can be committed and diffed. Generate a mess,
then run `cleanup` on it: that pairing is the demo.

### Two standing caveats

Both are stated in the skills and in the output itself, not buried here.

**The VAT declaration is not the official form.** It gets the figures right and
proves the journals tie to the declaration, but the справка-декларация's numbered
cells could not be verified from any accessible source, so the declaration uses
descriptive labels and `config/vat-rates.yaml` ships `declaration_cells` empty for
someone with the НАП spec to fill in. A wrong cell number on a filed return is
worse than a missing one.

**The chart of accounts is illustrative.** `config/coa.yaml` follows the
conventional Bulgarian group structure but is not verified against the statutory
сметкоплан, which research did not turn up in citable form. It is one file to
replace, and unmapped accounts are reported rather than dropped.

**There is no cash flow statement.** That needs movement analysis, not a trial
balance. With a prior period you get a cash movement summary, labelled as such.

## Design notes

- **Money is never a float.** `Decimal` in Python, a fixed-point representation in
  JavaScript. An accountant who sees `0.30000000000000004` in a VAT total never trusts the
  tool again.
- **Rules live in config, not code.** VAT rates and the chart of accounts are data files.
  When a rate changes, you edit YAML, not source.
- **The libraries stand alone.** Delete the Claude skills and the CLI still works. Claude
  is the interface, not a load-bearing part of the arithmetic.
- **Two languages, one behaviour.** `tools/check_parity.py` runs both implementations
  over every sample file and diffs the output workbooks cell by cell, so they cannot
  drift apart silently. It has already caught one real bug: openpyxl and exceljs
  disagreed about whether an empty string is a blank cell.

## Not what this is

Not a commercial accounting package, and not tax advice. It computes; you decide what to
file. There is no direct submission to НАП — output is spreadsheets a human reviews.

## Further reading

- [Claude for financial services: skills](https://claude.com/resources/tutorials/claude-for-financial-services-skills)
  — Anthropic's tutorial on building skills for finance work
