---
name: euro-restatement
description: Use when converting Bulgarian accounting figures between BGN and EUR for the 2026 euro changeover — restating prior-year comparatives, handling January 2026 dual-currency statements, or checking a conversion someone did by hand. Triggers on "convert to euro", "restate 2025 figures", "прехвърли в евро", "check this conversion".
---

# Euro Restatement

Bulgaria adopted the euro on **1 January 2026** at the fixed, irrevocable rate
of **1 EUR = 1.95583 BGN**. This skill restates figures across that boundary.

## The rules that are not negotiable

- **The rate is fixed.** 1.95583 BGN to the euro. Never look up a market rate,
  never use a rate for a specific date, never let the user talk you into a
  different figure. This is law, not a market quote.
- **Round half up to two decimals.** Not banker's rounding. 0.025 becomes 0.03.
- **Never chain conversions.** Always convert from the originally recorded
  amount. Converting BGN to EUR and back must not drift, and it will if an
  already-rounded figure is converted again.
- **Currency by date, unless stated.** A transaction before 2026-01-01 is
  presumed BGN; on or after, EUR. An explicit currency column always wins.

## Running a restatement

Read `config/runtime.yaml` for the runtime, then:

| Runtime | Restate to EUR | Restate to BGN |
|---|---|---|
| `python` | `python -m iconomics cleanup --in <file> --out output/` | add `--currency BGN` |
| `node` | `node js/bin/iconomics.js cleanup --in <file> --out output/` | add `--currency BGN` |

The `Changes` sheet in the output records every converted amount with the before
value, the after value, and the rate used. That sheet is the evidence for the
restatement — point the user at it.

## January 2026 is the interesting month

For one month, 1–31 January 2026, both currencies were legal tender for cash.
Real January ledgers therefore contain both, often with an explicit currency
column. Expect a single file to mix them, and expect the mix to be legitimate
rather than an error. `data/raw/ledger-2026-01.xlsx` is exactly this case.

Do not "correct" a BGN row dated January 2026. Restate it and log it.

## Checking someone else's conversion

When asked to verify a hand-done conversion, compute the expected figure and
compare. The common errors, in the order you should suspect them:

1. Rounding half-even instead of half-up, giving a one-cent difference on
   figures ending in exactly half a cent.
2. Multiplying where they should have divided — BGN to EUR is a division by
   1.95583, and the euro figure must be the smaller one.
3. Converting a total that was itself computed from already-converted rows,
   compounding two roundings.

State the discrepancy in cents and name which of these it looks like. Do not
describe a one-cent difference as an error without first checking the rounding
rule — it usually is the rounding rule.
