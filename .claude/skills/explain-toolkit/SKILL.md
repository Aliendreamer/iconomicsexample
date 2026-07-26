---
name: explain-toolkit
description: Use when the user asks how or why the toolkit works — what a skill does, why a design decision was made, whether a figure is correct, or what a Bulgarian accounting rule actually requires. Searches the web when the repository does not hold the answer. Triggers on "how does this work", "why did you", "explain the", "is that right?", "what does this skill do", "защо", "как работи".
---

# Explain the Toolkit

Answers questions about iconomics: what the skills do, how the code works, why it
was built this way, and what the underlying accounting rules require.

The hard part is not finding information. It is knowing **which kind of claim you
are making**, because each kind has a different standard of proof, and mixing them
up is how a confident wrong answer gets produced.

## Step 1 — Classify the question first

Do this before opening any file. Four kinds, four different sources:

| Kind of question | Example | Where the answer must come from |
|---|---|---|
| **Behaviour** — what the code does | "Does it round 0.025 up or down?" | The source, or better, **run it and read the output** |
| **Rationale** — why it was built this way | "Why not just use floats?" | The catalog below, the design spec, or code comments |
| **Regulation** — what the law requires | "When is the VAT return due?" | A **citable source**. Never memory, never inference |
| **Capability** — what a skill will do for the user | "Can it handle my bank export?" | The relevant `SKILL.md`, and say plainly if the answer is no |

If a question mixes kinds — "is 1.95583 right and why do you hardcode it?" — split
it and answer each part to its own standard. The rate is a regulation claim
needing a source; hardcoding it is a rationale claim.

## Step 2 — Read the repository before searching

Almost every question about this project is answered locally. Route by topic:

| Topic | Read |
|---|---|
| What a skill does, and when | `.claude/skills/<name>/SKILL.md` |
| Invariants, contracts, gotchas | `CLAUDE.md` |
| Why the architecture is shaped this way | `docs/superpowers/specs/2026-07-26-iconomics-design.md` |
| Money, rounding, currency conversion | `py/src/iconomics/money.py` |
| Date and amount parsing rules | `py/src/iconomics/parsing.py`, function `_resolve_separators` |
| What happens to a bad row | `py/src/iconomics/workbook.py`, function `load` |
| Vendor merging, the change log | `py/src/iconomics/cleanup.py` |
| VAT classification and the declaration | `py/src/iconomics/vat.py` |
| Statement roll-up and the balance checks | `py/src/iconomics/statements.py` |
| Bank matching tiers | `py/src/iconomics/reconcile.py` |
| Account code → statement line | `py/src/iconomics/coa.py`, `config/coa.yaml` |
| Sample data and what is planted in it | `tools/make_sample_data.py` |
| Whether the two languages still agree | `tools/check_parity.py` — run it |

**Prefer demonstrating to asserting.** For any behaviour question, running the
command and quoting the real output is both faster and more convincing than
describing the code. "Here is what it actually did" ends an argument that "the
code should do this" only starts.

## Step 3 — Search the web when, and only when, needed

Search for:

- **Anything regulatory**: VAT rates, filing deadlines, SAF-T phase-in thresholds,
  the statutory chart of accounts, reporting formats. These change, and the
  repository's notes were researched on **2026-07-26** — treat them as possibly
  stale, especially if this conversation is much later than that.
- **Library behaviour** you are not certain of in openpyxl, exceljs, or decimal.js.
- **Anything the user challenges** where the repository is silent.

Do not search for:

- What this code does. Read it, or run it.
- Why a decision was made here. That is in the spec and the catalog below.
- Arithmetic you can verify yourself.

**Cite what you find**, with links. When a source contradicts something in
`CLAUDE.md` or the spec, say so explicitly and treat the fresher cited source as
correct — then offer to update the repository, because a stale note that has been
noticed and left is worse than one nobody has checked.

If searching turns up nothing solid, say that. "I could not find an authoritative
source for the statutory account codes" is a real, useful answer — it is in fact
the exact reason `config/coa.yaml` is designed to be replaced rather than trusted.

## The rationale catalog

These are the decisions users ask about. Each has a reason that is not derivable
from reading the code, which is why they are written down.

**Money is `Decimal` / `decimal.js`, never a float.**
Binary floating point cannot represent 0.1 exactly. An accountant who sees
`0.30000000000000004` in a VAT total stops trusting the tool permanently, and they
are right to. The single permitted float is in `_serialize`, where a value is
leaving into a spreadsheet cell after all arithmetic is finished and will never be
read back for computation.

**Rounding is half-up, not banker's rounding.**
Python's default for `Decimal.quantize` is half-even, which turns 0.025 into 0.02.
Bulgarian accounting practice — and every accountant's instinct — expects 0.03.
The rounding mode is passed explicitly at every call site in both languages rather
than set globally, so another module cannot silently change it.

**The euro rate is a hardcoded constant, not configuration.**
1 EUR = 1.95583 BGN is fixed and irrevocable by law, not a market quote. Making it
configurable would invite someone to "update" it, which would be wrong in every
case. Rates that genuinely change — VAT — live in config; this one cannot.

**Every row carries `source_row`.**
Any figure in any output can be traced back to the exact cell it came from. This
is the property that makes output auditable, and it is what an accountant needs
before they will sign anything. It is also why `data/raw/` is never written to: if
the original moves, the trace is worthless.

**Rejected rows go to an `Exceptions` sheet instead of being guessed at.**
A run reporting two exceptions out of fourteen has told the accountant exactly
where to spend attention. A run that quietly produced fourteen confident rows, two
of them wrong, has done real harm. Row-level problems therefore never abort the
run, while file-level problems — a missing required column — abort before anything
is written, because a half-correct financial statement is worse than none.

**There are two full implementations, Python and JavaScript.**
The audience for this demo reads JavaScript. A Python-only toolkit would ask them
to take the accounting logic on faith. The drift risk is real and is handled by
`tools/check_parity.py`, which diffs both implementations' output cell by cell.
It has already caught one genuine divergence: openpyxl reads an empty string back
as `None` while exceljs reads it back as `""`, so the two were writing different
cell types for the same blank.

**Dates are written as ISO strings, not date-typed cells.**
openpyxl and exceljs disagree about date cell representation, and a string is
unambiguous, sorts correctly, and compares cleanly across both. The cost is that
Excel shows text rather than a date — accepted, because the accountant's next step
is reading, not date arithmetic.

**Sample generation has no random number generator.**
Python's `random` and JavaScript's `Math.random` cannot be made to agree, and
generated files must be identical from both implementations. So wrinkles are
injected at fixed row indices and all money is computed in integer cents.

**Rules live in YAML, not source.**
An accountant can add a header alias or change a VAT rate without touching Python.
That is the difference between a tool they can maintain and a tool they must file a
request against.

**The VAT declaration derives its totals from the journal rows.**
It does not compute them alongside. A return whose declaration disagrees with its
journals is rejected, and the usual cause is two independent computations drifting.
With one computation they cannot disagree, and a `Reconciliation` sheet shows it.

**The VAT declaration uses descriptive labels, not official cell numbers.**
Research on 2026-07-26 found confirmation of the return's *structure* — declaration
plus purchase and sales journals, filed by the 14th — but no citable listing of the
numbered cells. `config/vat-rates.yaml` therefore ships `declaration_cells` empty
for someone with the НАП form spec to fill in. A wrong cell number on a filed
return is worse than a missing one. This is the same reasoning as the chart of
accounts: where the authoritative source could not be verified, the toolkit is
built to be corrected rather than trusted.

**Statement figures are aggregated debit-positive internally.**
Not in each account's "natural" direction. A statement line fed by accounts with
opposite normal sides — a VAT receivable and a VAT payable — would add instead of
offset. Direction is applied only for presentation, so revenue and liabilities
still read positive. This was a real bug caught while building the sample trial
balance, not a hypothetical.

**Financial statements refuse to emit when they do not balance.**
Both the input trial balance and the resulting balance sheet are checked, and
failure aborts before anything is written. Someone will read a financial
statement, so a half-correct one is worse than none.

**Bank matching is tiered, and only `exact` is an answer.**
`probable` and `possible` are proposals for a human. A wrong match hides a real
discrepancy, which is the exact failure a reconciliation exists to catch. The
known limitation is that counterparty matching is textual, so a latinised
narration (`EPSILON EOOD`) will not recognise a Cyrillic ledger name
(`Епсилон ЕООД`) and gets demoted to `possible`.

**There is no test suite.**
A deliberate choice for a demonstration project — the owner asked for it kept
uncluttered. `tools/check_parity.py` is the one safety net. Do not add a test
framework unless asked, and if a user asks why there are no tests, this is the
honest answer rather than an oversight.

## Step 4 — Shape the answer for who is asking

The same question needs a different answer depending on the reader, and you can
usually tell from how they phrase it.

**An accountant** asking "why is this row missing?" wants: which row, what was
wrong with it, what to do about it. Answer in their vocabulary — счетоводна сметка,
данъчна основа, дневник — not in field names. Never make them read code to get an
answer that a sentence would give.

**A developer** asking the same thing wants the control flow: `load` catches
`UnparseableAmount`, appends a `Problem`, continues. Name the file and function so
they can go look.

**Someone evaluating Claude Code** is really asking a different question: was this
worth building this way? Answer it directly, including the costs. Two
implementations is genuinely twice the maintenance; the parity check is what makes
it defensible rather than reckless.

When you cannot tell, ask — one question, then answer properly.

## Honesty rules

- **Never state a regulatory fact from memory.** Search, cite, or say you are not
  sure. A wrong filing deadline has consequences a wrong variable name does not.
- **Distinguish "the code does" from "the code should".** If you find a bug while
  explaining, say so plainly and separately from the explanation.
- **Do not defend a decision you think is wrong.** The catalog above is reasoning,
  not doctrine. If a user makes a better argument, say so — and note it as
  something worth changing rather than quietly conceding.
- **Never invent a citation.** No plausible-looking URLs, no "according to НАП"
  without a source you actually retrieved.
- **Say when something is not built.** All four workflows now exist in both
  languages, and `tools/check_parity.py` verifies all five subcommands cell by
  cell. SAF-T export remains deliberately deferred — do not describe it as
  available. Neither is a statutory cash flow statement.

## Worked examples

**"Why does it say 1234 when my file says 1.234?"**
Behaviour question. Read `_resolve_separators` and quote the rule: a single
separator followed by exactly three digits is treated as a thousands separator, so
`1.234` is one thousand two hundred thirty-four while `12.50` is twelve fifty.
Then say where it is logged, and offer to check whether the VAT on that row is
consistent with the interpretation — for the March sample it is, which confirms the
reading. Mention this is a documented judgement call, not a bug.

**"Is the 9% rate right for hotels?"**
Regulation question. Do not answer from memory even though `CLAUDE.md` says 9% for
accommodation. Search, cite, and confirm — and note the note's research date.

**"Could this do my bank reconciliation?"**
Capability question. Yes: `iconomics reconcile --bank … --ledger …`, in either
language. Then state the thing that shapes what they get — matching is tiered and
only `exact` is settled. Do not oversell a `possible` match as a result.

**"Can I file the VAT return this produces?"**
Capability question with a regulatory edge, and the answer is no. It gets the
figures right and proves the journals tie to the declaration, but the declaration
uses descriptive labels rather than official НАП cell numbers, which were not
verifiable. It is a working paper. Say so first, before describing what it does
well — a user who files it because you buried the caveat has been badly served.

**"Why two languages? Seems like a waste."**
Rationale, and a fair challenge. Give the reason, concede the cost honestly, and
point at `check_parity.py` as the thing that makes it defensible. Do not oversell.
