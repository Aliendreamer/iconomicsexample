---
name: bank-reconciliation
description: Use when matching a bank statement against a ledger — finding which payments cleared, which are missing, and which bank lines have no ledger entry. Triggers on "reconcile the bank statement", "match these payments", "what hasn't cleared", "равни ли са с банката", "изравни банката".
---

# Bank Reconciliation

Matches bank statement lines against ledger entries and reports what does not
line up. This is the job accountants most want to stop doing by hand.

**Runtime: Python only.** The JavaScript implementation of this workflow is not
built yet. Ignore `config/runtime.yaml` for this command and use Python — if the
user has it set to `node`, say so rather than failing silently.

```
python -m iconomics reconcile --bank <statement.xlsx> --ledger <ledger.xlsx> \
    --out output/ [--window 5] [--currency EUR]
```

## The tiers, and why only one of them is an answer

Matching is tiered, and the tier is the point. Never collapse them.

| Tier | Basis | Status |
|---|---|---|
| `exact` | Amount, date and counterparty all agree | Settled |
| `probable` | Amount agrees, date within the window, counterparty recognisable | **Proposal — needs a human** |
| `possible` | Amount agrees, nothing else corroborates | **Proposal — needs a human** |

`exact` matches go to the `Matched` sheet. Everything else goes to `Proposed`,
and you must present them as questions, not results. A wrong match hides a real
discrepancy, which is the precise failure a reconciliation exists to catch —
presenting a `possible` as settled defeats the entire exercise.

## Procedure

1. **Identify both files.** A bank statement and a ledger. If the user names only
   one, list `data/raw/*.xlsx` and ask which is which. Do not guess from filenames.
2. **Run the command.**
3. **Report in this order** — it is ordered by what obliges action:
   - **Bank lines with no ledger entry.** Something left the account that the
     books do not know about. Bank charges, direct debits, fraud. Highest priority.
   - **Ledger rows not on the statement.** Unpresented payments, or something
     recorded that never actually moved.
   - **Proposed matches** to confirm or reject, each with its tier and day gap.
   - **Confirmed matches**, as a count and total. Do not enumerate these.
4. **Offer to widen the window** if many rows are unmatched. `--window` defaults
   to 5 days; bank value dates can lag invoice dates further at month end.

## What it does automatically, and will tell you about

**It restates currencies.** An amount cannot be matched across currencies, and
real March 2026 ledgers still contain BGN correction entries. Rows are converted
to the target currency at the fixed 1.95583 rate before matching, and the count
appears in the `Summary` sheet as "Rows restated". Mention it when it is non-zero.

**It consumes each row once.** Matching is greedy, best tier first, so a clean
pairing is never stolen by a weaker candidate. It is deterministic — same inputs,
same pairing, every time.

## Known limitation worth stating

Counterparty matching is textual, so **a transliterated name will not be
recognised**. A statement narration reading `EPSILON EOOD` against a ledger
counterparty of `Епсилон ЕООД` is the same company, but the match will be demoted
to `possible` rather than `probable`, because the strings share nothing.

This is visible in the sample data and is not a bug to hide — it is a real
property of Bulgarian bank exports, which sometimes latinise names. Tell the user
when you see it, because those proposals are usually correct and they can confirm
them quickly once they know why the tier is low.

## Do not

- Do not edit either input file. Both are evidence.
- Do not "resolve" a discrepancy by assuming a fee or a rounding difference. Report
  the gap and its amount; the accountant decides what it was.
- Do not report a total of matched value as though it proves the account
  reconciles. It reconciles when the unmatched lists are explained, not when the
  matched total looks large.
