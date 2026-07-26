---
name: financial-statements
description: Use when rolling a trial balance into financial statements — profit and loss, balance sheet, prior-year comparatives restated to euro. Triggers on "produce the P&L", "balance sheet", "ОПР и баланс", "annual financial statements", "roll up the trial balance".
---

# Financial Statements

Rolls a trial balance into a profit and loss account and a balance sheet, with
prior-period comparatives restated to the target currency.

**Runtime: Python only.** The JavaScript implementation of this workflow is not
built yet. Use Python regardless of `config/runtime.yaml`, and say so if the user
has it set to `node`.

```
python -m iconomics statements --in <trial-balance.xlsx> --out output/ \
    [--prior <prior-tb.xlsx>] [--prior-currency BGN] [--currency EUR]
```

## What the input must contain

A trial balance: an **account code** column, and **debit** and **credit** columns
(`Сметка`, `Дебит`, `Кредит`). No dates — a trial balance has none, which is why
it uses a different loader from a ledger.

## The euro comparative is the interesting part

A 2025 comparative is in BGN; the 2026 current period is in EUR. Pass
`--prior-currency BGN` and the prior trial balance is restated at the fixed
1.95583 rate before comparison. Conversion is from the originally recorded
amounts, never chained, so it cannot drift.

Without `--prior`, the comparative columns are blank rather than zero — blank
means "not supplied", zero would be a claim about last year.

## It refuses to produce a wrong statement

Two invariants are enforced, and both abort the run **before anything is
written**:

1. **The trial balance must balance.** Debits must equal credits. If they do not,
   nothing is produced, and the error names both totals.
2. **The balance sheet must balance afterwards.** Assets must equal equity plus
   liabilities plus the period result. If not, an account is mapped to the wrong
   statement or side in `config/coa.yaml`, and the error says so.

This is deliberate. A half-correct financial statement is worse than none —
someone will read it. When you hit either error, report it as a finding about the
data or the mapping, not as a tool failure, and go look at the named accounts.

The output carries a `Checks` sheet recording both. Confirm it and say so.

## ⚠ The chart of accounts is illustrative

`config/coa.yaml` maps account codes to statement lines. Bulgarian law requires a
statutory сметкоплан, but research on 2026-07-26 did **not** find a citable
listing of the statutory codes. The shipped codes follow the conventional group
structure (2x assets, 4x settlements, 5x cash, 6x expenses, 7x revenue) and are
explicitly marked as unverified.

**Always say this.** Then offer the fix, which is genuinely quick: the user's
accountant knows the real codes, and replacing `config/coa.yaml` is a one-file
edit. Accounts not in the file appear in an `Unmapped Accounts` sheet rather than
being dropped — that sheet is the punch list for correcting the mapping.

Sub-accounts roll up automatically: booking to `6021` resolves to `602` by walking
the code down, so a firm's own sub-accounts work without extra configuration.

## ⚠ There is no cash flow statement

A statutory cash flow statement requires movement analysis, not a single trial
balance. It is **not** produced, and the `Checks` sheet says so.

What you get instead, when `--prior` is supplied, is a `Парични средства` sheet:
opening and closing balances per cash account with the movement between them.
That is a cash movement summary. Call it that. Do not describe it as a cash flow
statement, and do not let it be mistaken for one — the difference matters to
anyone filing.

## Procedure

1. Run the command. Add `--prior` and `--prior-currency BGN` if a comparative
   exists — it almost always does and it is the most useful column on the page.
2. If it aborts, report which invariant failed and the figures involved. That is
   the finding.
3. Report the period result and total assets, then confirm the `Checks` sheet.
4. List anything in `Unmapped Accounts` — those lines are missing from the
   statements entirely, so the figures are incomplete until they are mapped.
5. State the two caveats above: illustrative chart of accounts, and no cash flow
   statement.

## Do not

- Do not adjust the trial balance to make it balance. An unbalanced trial balance
  is a real problem in the bookkeeping, and hiding it is the worst thing the tool
  could do.
- Do not present these as filed accounts. They are working papers — no notes, no
  accounting policies, no directors' report, and none of the disclosure a
  statutory annual filing requires.
