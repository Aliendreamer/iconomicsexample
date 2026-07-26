---
name: generate-ledger
description: Use when the user wants sample or test ledger data as an .xlsx file — a practice file, a demo dataset, something to try a workflow against, or a large file to check performance. Triggers on "generate a ledger", "make me some test data", "create a sample xlsx", "I need a file with 200 rows", "направи тестови данни".
---

# Generate a Ledger

Produces an `.xlsx` export shaped like a real Bulgarian accounting extract, at a
size and messiness the user chooses.

Generation is fully deterministic. The same arguments always produce the same
file, so a generated fixture can be committed and diffed. Say this if the user
asks whether the data is random — it is not, and that is deliberate.

## Ask before generating

Two things decide the output. If the user has not said, ask — but ask for both in
**one** message, not two.

**How many rows?** Any whole number. Useful reference points:

| Rows | Good for |
|---|---|
| 10–20 | Reading the whole thing by eye; learning what the tool does |
| 50–100 | Realistic monthly volume for a small company |
| 500+ | Checking that a workflow holds up on real volume |

**How messy?** Three levels, and the choice matters more than the row count:

| Level | What it contains | Use when |
|---|---|---|
| `clean` | ISO dates, dot decimals, one spelling per vendor, all EUR. Produces zero exceptions. | The user wants a well-formed baseline, or input for another tool |
| `messy` | Bulgarian `dd.mm.yyyy` dates, comma decimals with space thousands, vendor case and spacing variants, some rows still booked in BGN, the occasional Excel serial date | The realistic default — this is what exports actually look like |
| `nasty` | Everything in `messy`, plus unreadable amounts (em dashes), blank dates, blank counterparties, credit notes in accounting parentheses, duplicated transactions, an unrecognized extra column, and the alternate `Партньор` header | Demonstrating exception handling, or stress-testing a workflow |

Default to `messy` if the user expresses no preference. Default to 20 rows.

Optionally `--period YYYY-MM` sets the month the rows are dated in; it defaults to
`2026-03`. Use `2025-12` or earlier if the user wants pre-euro BGN data, or
`2026-01` for the dual-circulation month.

## Run it

Read `config/runtime.yaml` for the runtime, then:

| Runtime | Command |
|---|---|
| `python` | `python -m iconomics generate --rows N --complexity LEVEL --out PATH.xlsx` |
| `node` | `node js/bin/iconomics.js generate --rows N --complexity LEVEL --out PATH.xlsx` |

Both produce identical files — `tools/check_parity.py` verifies this.

**`--out` is a file path here, not a directory.** This differs from `cleanup`,
whose `--out` is a directory. Getting it wrong writes a file with no extension.

Put generated files somewhere that is not `data/raw/` unless the user explicitly
wants a new committed sample — `data/raw/` holds the curated fixtures, and
cluttering it makes `check_parity.py` slower for everyone.

## After generating

Say how many rows, at which level, and where the file is. Then offer the obvious
next step: running `cleanup` on it. That pairing is the whole point — generate a
mess, then watch it get resolved with a full audit trail.

If the user chose `nasty`, mention roughly what to expect from a cleanup run: at
40 rows it produces a handful of exceptions and a couple of dozen logged changes.
Do not state exact counts you have not seen — run it and read the summary.

## What this is not

Not anonymized real data, and not a fixture for testing tax correctness. The VAT
figures are arithmetically consistent with the stated rate, but the transactions
are invented and the vendors are fictional. Do not present generated output as
evidence about anyone's actual books.
