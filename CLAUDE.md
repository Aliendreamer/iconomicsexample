# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Bulgarian accounting toolkit, built as a demonstration of doing accounting work
with Claude Code. It is implemented **twice** — Python and JavaScript — because
the intended audience reads JS and a Python-only version would ask them to take
the accounting logic on faith.

Design spec: `docs/superpowers/specs/2026-07-26-iconomics-design.md`.
Implementation plan (partly superseded by the built code): `docs/superpowers/plans/`.

## Commands

This machine has **no `pip` and no `python3-venv`** — use `uv`. The venv lives at
the repo root, not inside `py/`.

```bash
uv venv --python 3.12                    # once
uv pip install -e py/                     # once, after cloning
npm --prefix js install                  # once

.venv/bin/python tools/make_sample_data.py    # regenerate data/raw/ (deterministic)
.venv/bin/python tools/check_parity.py        # verify Python and JS still agree

# Run a workflow — these two are interchangeable and produce identical output
.venv/bin/python -m iconomics cleanup --in data/raw/ledger-2026-03.xlsx --out output/
node js/bin/iconomics.js cleanup --in data/raw/ledger-2026-03.xlsx --out output-js/

# Generate sample data. Note --out is a FILE here, unlike cleanup's directory.
.venv/bin/python -m iconomics generate --rows 100 --complexity nasty --out /tmp/practice.xlsx
```

Add `--currency BGN` to restate into BGN instead of EUR.

**There is no test suite** — this is a demonstration project and it was a
deliberate choice to keep it uncluttered. `tools/check_parity.py` is the one
safety net: it runs both implementations over every sample file and diffs the
output workbooks cell by cell. Run it after touching anything in `py/src/` or
`js/src/`. Do not add a test framework without being asked.

## Architecture

Three layers, deliberately separated:

```
.claude/skills/*     Thin. Name a CLI subcommand, interpret the result for a
                     human. No logic. Read config/runtime.yaml to choose runtime.
py/src/iconomics/    All computation, in Python.
js/src/              All computation, in JavaScript. Same behaviour, same CLI.
config/*.yaml        The rules — header aliases, and later VAT rates and the
                     chart of accounts. Editable by an accountant.
data/raw/            Deliberately messy sample inputs (committed).
```

The libraries stand alone. Delete `.claude/` and everything still works — Claude
is the interface, not part of the arithmetic.

### Skills

| Skill | Role |
|---|---|
| `ledger-workflow` | Orchestrator — sequences the four below and reports once |
| `generate-ledger` | Deterministic sample data at three complexity levels |
| `ledger-cleanup` | The cleanup workflow |
| `euro-restatement` | BGN⇄EUR rules, and verifying someone else's conversion |
| `exception-triage` | Working through rejected rows with the user |

`ledger-workflow` must not reimplement the others — it reads their `SKILL.md` at
each stage. When changing a single-purpose skill, check whether the orchestrator's
description of that stage is still accurate.

Modules mirror each other one-for-one across languages:

| Module | Responsibility |
|---|---|
| `money` | `Money` type, the fixed BGN⇄EUR conversion, half-up rounding |
| `parsing` | Pure parsers for messy dates, amounts, and header/vendor names |
| `config` | Loads the YAML rule files; walks up to find `config/` |
| `workbook` | **The only module that touches `.xlsx`.** Load → canonical rows; write → formatted sheets |
| `cleanup` | The cleanup workflow: vendor normalization, currency restatement, change log |
| `generate` | Deterministic sample-data generation at three complexity levels |
| `cli` / `bin/iconomics.js` | Argument parsing, the stdout summary, exit codes |

### Why `generate` has no random number generator

Generation must produce byte-identical files from both implementations, and
Python's `random` and JavaScript's `Math.random` cannot be made to agree. So every
wrinkle is injected at a **fixed row index** (`index % 11 == 5` gets an em dash,
`index % 23 == 3` becomes a credit note, and so on) and all money is computed in
**integer cents**. If you extend the generator, keep both properties — and watch
for `str.replace` vs `String.replace`, which differ: Python replaces every
occurrence, JavaScript only the first. Use `replaceAll` in JS.

## Invariants — do not break these

- **No float money.** `Decimal` in Python, `decimal.js` in JavaScript. The single
  permitted exception is `_serialize`/`serialize` in `workbook`, where a value is
  leaving into a spreadsheet cell after all arithmetic is complete.
- **The euro rate is a constant:** 1 EUR = 1.95583 BGN, fixed and irrevocable
  since 2026-01-01. Never fetch it, never make it configurable.
- **Rounding is half-up to 2dp**, never banker's rounding.
- **Every row carries `source_row`** (`sourceRow` in JS) — the 1-indexed original
  spreadsheet row. This is the spine of the audit trail; never drop it.
- **Row-level problems do not abort; file-level problems do.** A bad amount
  becomes a `Problem` and the run continues. A missing required column raises
  `MissingColumn` before any output is written.
- **Never silently guess or drop.** Rejected rows land in the `Exceptions` sheet
  with a reason. Unmapped columns are preserved in `extra`.
- **Never write to `data/raw/`** outside `tools/make_sample_data.py`. The
  untouched original is what makes the audit trail credible.

## Cross-language contracts

These exist so `tools/check_parity.py` can compare the two implementations cell by
cell. Changing one side without the other makes that check fail.

1. **Sheet names and column headers are identical**: `Clean`, `Changes`,
   `Exceptions`, with the headers defined in `cleanup.CLEAN_COLUMNS` etc.
2. **Dates are written as ISO strings** (`2026-03-01`), not date-typed cells —
   openpyxl and exceljs disagree about date cell representation.
3. **An empty string is written as a blank cell** in both. openpyxl reads `""`
   back as `None` while exceljs reads it back as `""`, so both serializers
   normalize `""` to null.
4. **The stdout summary is byte-identical**, including label padding.
5. **`Money.__str__` / `toString()` render at least two decimals.** Python's
   `Decimal` keeps its constructed scale (`Decimal("42")` → `"42"`) while
   decimal.js normalizes it away, so both sides apply an explicit
   `max(2, decimal_places)` rule. These strings appear in the `Changes` sheet.

Field naming differs by idiom and that is fine: `source_row` ⇄ `sourceRow`,
`amount_net` ⇄ `amountNet`. Only the *spreadsheet* headers must match.

## Domain facts worth knowing

- Bulgaria joined the euro **2026-01-01**; dual cash circulation ran through
  2026-01-31, so a January ledger legitimately contains both currencies.
- VAT: **20%** standard, **9%** reduced (accommodation, publications, certain
  baby products), **0%** intra-EU supply. Monthly return due the **14th**.
- A Bulgarian VAT return is three linked documents: sales journal, purchase
  journal, and the declaration — plus a VIES declaration for intra-EU B2B.
- Dates in Bulgarian exports are **day-first** (`01.02.2026` is 1 February).
- Amounts commonly use **comma as the decimal separator** and space or dot for
  thousands. `parsing` resolves this; see the rule in `_resolve_separators`.

## Known gap

`config/coa.yaml` does not exist yet, and when it does its account codes will be
**illustrative**. Research did not turn up a citable listing of the statutory
Bulgarian сметкоплан, so the chart of accounts is treated as data to be replaced
by the firm's real one. Do not hardcode account numbers.

## Not yet built

`bank-reconciliation`, `bg-vat-return`, and `financial-statements` are specified
but not implemented. SAF-T export is deliberately deferred as a separate project.
