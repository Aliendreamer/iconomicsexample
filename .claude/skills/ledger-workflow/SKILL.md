---
name: ledger-workflow
description: Use when the user wants the whole pipeline run end to end rather than one step — pick files, clean them, restate the currency, and work through the exceptions in one pass. Triggers on "run the whole workflow", "process these files", "do the full run", "take it from here", "обработи всичко".
---

# Ledger Workflow

Runs the single-purpose skills as one sequence:

```
generate-ledger  →  ledger-cleanup  →  euro-restatement  →  exception-triage
   (optional)          (per file)        (verification)      (interactive)
                            │
                            └─ then, if the data supports them:
                                 bank-reconciliation   (needs a bank statement)
                                 bg-vat-return         (needs rates + direction)
                                 financial-statements  (needs a trial balance)
```

Each stage is a skill in its own right. This skill decides the order, carries
results between stages, and produces one consolidated report at the end. It does
not reimplement any of them — read the relevant `SKILL.md` when you reach its
stage and follow it.

**The last three are conditional, not optional.** Run them when the inputs are
present and skip them when they are not — but say which you skipped and why. A
user who supplied only a ledger should be told that a VAT return needs a rate and
a direction column, not left wondering why no return appeared.

## Stage 0 — Choose the inputs

**Always start here, and always ask.** Never assume which files the user means.

1. List what is available: `ls data/raw/*.xlsx`, plus anything the user has
   mentioned in this conversation.
2. Present the list and ask which to process. Accept "all of them", a subset, a
   glob, or a path outside the repo.
3. If there are no files, or the user says they have nothing yet, offer to
   generate some — that is the `generate-ledger` stage below.

Then ask, in the **same** message, the two things that change the output:

- **Target currency** — EUR (default, correct for 2026 onward) or BGN.
- **Where the output goes** — default `output/`. Never `data/raw/`.

Do not ask anything else up front. Everything remaining can be decided from what
the run actually produces.

## Stage 1 — Generate (only if needed)

Skip entirely if the user has files. Otherwise follow `generate-ledger`: ask for
row count and complexity, generate, then continue with that file as the input.

Write generated files to the output directory or `/tmp`, not `data/raw/`.

## Stage 2 — Clean each file

Follow `ledger-cleanup` for every selected file, in a stable order (alphabetical).

Read `config/runtime.yaml` once at the start and use the same runtime for the
whole run. Never switch mid-workflow — mixing them makes a consolidated report
meaningless even though the output would be identical.

Collect from each run: rows in, rows clean, changes, exceptions, output path.

**If a file fails with a missing-column error, do not stop the whole run.** Record
it, continue with the remaining files, and report the failure at the end. One
malformed export should not cost the user the other five results.

## Stage 3 — Verify the restatement

Follow `euro-restatement` as a check rather than a conversion, because Stage 2
already converted. Confirm on the output:

- Every row in the `Clean` sheet carries the target currency.
- Every conversion in `Changes` cites the fixed rate 1.95583.
- Pre-2026 files converted; files already in the target currency did not.

If a file dated 2026 or later contained BGN rows, say so explicitly — those are
correction entries booked after the changeover, and they are the single most
interesting thing the workflow surfaces about real books.

## Stage 4 — Triage the exceptions

Follow `exception-triage` across **all** files at once, not file by file. Group by
reason, because the same cause usually spans several files and one config fix
often resolves the lot.

This stage is interactive. Stop and ask; do not decide on the user's behalf what
an unreadable value meant. If they ask you to add header aliases to
`config/headers.yaml`, do it, then re-run Stage 2 for the affected files only and
report the new exception counts.

## Stage 4b — The conditional workflows

After triage, check what the selected inputs actually support and run what they do.
Classify each file once, at Stage 0, so this is a lookup rather than a guess:

| If the inputs include | Run | Skill to follow |
|---|---|---|
| A bank statement **and** a ledger | `iconomics reconcile` | `bank-reconciliation` |
| A ledger with a VAT rate column **and** a direction column or account codes | `iconomics vat-return` | `bg-vat-return` |
| A trial balance (account + debit + credit columns) | `iconomics statements` | `financial-statements` |

All three exist in both languages, so the one-runtime rule holds for the whole
run — keep using whatever `config/runtime.yaml` selected at Stage 0.

Two of these carry standing caveats that must reach the user, not just the log:
the VAT declaration is **not** the official НАП form, and the chart of accounts is
**illustrative**. Their own skills explain both; do not paraphrase them away.

## Stage 5 — Consolidated report

Finish with one table, not a wall of per-file summaries:

| File | Rows in | Clean | Changes | Exceptions |
|---|---|---|---|---|
| ledger-2026-01.xlsx | 5 | 5 | 4 | 0 |
| ledger-2026-03.xlsx | 14 | 13 | 4 | 1 |
| **Total** | **19** | **18** | **8** | **1** |

Then, in prose, and in this order of priority:

1. **What needs a human.** The outstanding exceptions, named by file and row.
   This is the only part that carries an obligation, so it goes first.
2. **What changed.** Totals by kind — how many vendor merges, how many rows
   restated from BGN.
3. **Where the files are.**
4. **Any files that failed** and why.

If nothing needs a human, say that plainly in one sentence rather than padding the
report to look thorough.

## Rules for the whole run

- **`data/raw/` is read-only.** The untouched original is what makes the audit
  trail credible. Generated and cleaned files go elsewhere.
- **Confirm before large runs.** More than about ten files, or any file over a few
  thousand rows, gets a "this will take a moment, proceed?" first.
- **Report what actually happened.** If a stage was skipped, say it was skipped.
  If a file failed, say so with the error. Never present a partial run as complete.
- **One runtime per run**, chosen at the start from `config/runtime.yaml`.
- **Do not invent figures.** Every number in the final report comes from a summary
  the CLI actually printed or a sheet you actually read.

## When not to use this skill

If the user asks for one specific thing — "just clean this file", "what does this
exception mean" — use the individual skill. This workflow earns its overhead on
several files or when the user wants to hand over the whole job; on a single file
with a single question it is ceremony.
