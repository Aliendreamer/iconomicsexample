---
name: ledger-cleanup
description: Use when the user has a messy accounting export to tidy up — inconsistent dates, amounts stored as text, duplicate vendor spellings, or mixed BGN and EUR rows. Triggers on "clean up this ledger", "these dates are a mess", "normalize this export", "оправи този файл".
---

# Ledger Cleanup

Turns a messy spreadsheet export into a clean, single-currency table with a full
audit trail. Everything the toolkit changes is logged; anything it cannot read
is set aside with a reason rather than guessed at.

## Pick the runtime

Read `config/runtime.yaml`. It says `python` or `node`. Use the matching command:

| Runtime | Command |
|---|---|
| `python` | `python -m iconomics cleanup --in <file> --out output/` |
| `node` | `node js/bin/iconomics.js cleanup --in <file> --out output/` |

Both produce identical output — never mix them in one session, and never
"translate" a command by hand. If the user asks for the other language, change
`config/runtime.yaml` rather than improvising.

Add `--currency BGN` only if the user explicitly wants BGN. The default is EUR,
which is correct for any period from 2026 onward.

## Procedure

1. **Find the input.** If the user did not name a file, list `data/raw/*.xlsx`
   and ask which one. Do not guess when more than one candidate exists.
2. **Run the command** for the configured runtime.
3. **Read the summary.** It reports rows in, rows clean, changes, exceptions,
   and the output path.
4. **Report the exceptions first.** These matter more than the successes — they
   are the rows the accountant must personally decide about. Open the
   `Exceptions` sheet and list each one as: source row, field, the raw value,
   and why it was rejected. Reference the row number so they can open the
   original file and look.
5. **Summarize the changes.** Group them: how many vendor spellings were merged,
   how many rows were restated from BGN to EUR. Do not list all of them
   individually unless asked or unless there are fewer than about ten.
6. **Point at the output file** and say what the three sheets are: `Clean`,
   `Changes`, `Exceptions`.

## What to tell the user, and what not to

State plainly that every clean row carries its original spreadsheet row number,
so any figure traces back to the cell it came from. That property is what makes
the output auditable, and it is the thing an accountant most needs to hear.

Do not describe an exception as a failure of the tool. A row set aside is the
tool working correctly — it declined to invent a value.

Never edit `data/raw/` files. The original export stays untouched; that is what
makes the audit trail credible.

## Known judgement calls

Two decisions are made automatically and are worth mentioning if the user's data
hits them:

- **Ambiguous decimal separators.** `1.234` is read as one thousand two hundred
  thirty-four, because a single separator followed by exactly three digits is
  treated as a thousands separator. `12.50` is read as twelve and a half. If a
  figure looks wrong by a factor of a thousand, this rule is why.
- **Vendor merging.** Spellings that differ only by case, spacing, or a trailing
  dot are merged into whichever variant appears most often. Ties go to the
  alphabetically first spelling, so the result is stable across runs.

Both are logged in the `Changes` sheet. Neither is silent.
