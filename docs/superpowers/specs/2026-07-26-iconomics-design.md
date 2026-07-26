# iconomics — Design Spec

**Date:** 2026-07-26
**Status:** Approved (step 1 of 2)
**Step 2 (separate spec):** SAF-T XML export

## Purpose

A working sample project that shows a practising Bulgarian accountant what it is like
to do their job with Claude Code. It has two jobs, and it fails if it does only one:

1. **Be genuinely useful.** The four workflows must produce output an accountant would
   actually file or hand to a client. A toy that only works on toy data proves nothing.
2. **Be legible as a demo.** The README narrates how a non-programmer drives Claude
   through these tasks, so the reader can picture doing it with their own books.

Audience is split, and both halves matter. An accountant who wants the tool must get it
working with one command (`pip install -e py/` or `npm --prefix js install`) and never need
to read code. A developer evaluating Claude Code must be able to read the accounting logic
in a language they know — hence the dual Python/JavaScript implementation described below.

No Excel installation required, cross-platform.

## Non-goals

- Not a commercial accounting package. No multi-company, no user management, no GUI.
- No SAF-T export (step 2).
- No e-invoicing, no direct filing to НАП. Output is spreadsheets a human reviews and files.
- No tax advice. The tool computes; the accountant decides.

## Context: why 2026 is the right year for this

Findings from research on 2026-07-26 that drive the design:

| Fact | Source | Design consequence |
|---|---|---|
| Bulgaria adopted the euro 2026-01-01 at the fixed irrevocable rate **€1 = 1.95583 BGN** | [Access2Markets](https://trade.ec.europa.eu/access-to-markets/en/news/bulgaria-adopts-euro-1-january-2026), [ECB](https://www.ecb.europa.eu/press/economic-bulletin/focus/2026/html/ecb.ebbox202508_01~b4379b735b.en.html) | Currency handling is cross-cutting, not a feature. Sample data straddles the changeover. |
| Dual circulation ran 2026-01-01 to 2026-01-31 | [Consilium](https://www.consilium.europa.eu/en/press/press-releases/2025/07/08/bulgaria-ready-to-use-the-euro-from-1-january-2026-council-takes-final-steps/) | January 2026 sample data legitimately mixes BGN and EUR cash entries. |
| VAT: 20% standard, 9% reduced (accommodation, publications, certain baby products), 0% intra-EU supply | [VATupdate](https://www.vatupdate.com/2026/02/10/bulgaria-comprehensive-vat-country-guide-2026/) | Rate table in config, not code. |
| VAT return = sales journal + purchase journal + declaration; monthly, due the 14th | [Sb Accounting](https://sb-bg.com/faq-items/what-does-the-bulgarian-vat-return-consist-of/) | Three linked outputs from one run, totals must tie. |
| VIES declaration required for intra-EU B2B, no threshold, same deadline | [aidosbg](https://aidosbg.com/vies-in-bulgaria/) | Fourth output sheet when intra-EU rows exist. |
| Registration threshold BGN 100,000 taxable turnover / 12 months | [AccountsOS](https://accounts-os.com/bg/questions/what-is-the-vat-rate-in-bulgaria) | Informational only; not enforced by the tool. |

The euro transition is the demo's centrepiece. Every accountant in the country is dealing
with it right now, and it is exactly the kind of mechanical, error-prone, high-volume
restatement work that is miserable by hand and trivial to automate.

## Architecture

Three layers, deliberately separated so each is understandable and testable alone.

```
.claude/skills/*        Thin. Instructions telling Claude which CLI command to run,
                        what to ask the user, how to present results. No logic.
py/src/iconomics/*      All computation, in Python.
js/src/*                All computation, in JavaScript. Same behaviour, same CLI.
data/ + config/         Sample inputs, golden outputs, and the rules (rates, accounts).
```

The libraries must be usable standalone. If someone deletes `.claude/`, both packages still
work and the tests still pass. This keeps the demo honest: Claude is the interface, not a
load-bearing part of the arithmetic.

## Dual implementation: Python and JavaScript

The audience for this demo reads JavaScript. A Python-only toolkit would ask them to take
the most interesting part — the actual accounting logic — on faith. So the toolkit is
implemented twice, in full.

The obvious risk is drift: six months from now the JavaScript rounds VAT one way and the
Python another, and nobody notices until a filed return is wrong. Three mechanisms prevent
that, and they are the reason this is a design decision rather than just twice the typing.

**1. A shared CLI contract.** Both implementations expose byte-identical command surfaces:

```
python -m iconomics vat-return --period 2026-03 --in data/raw --out output/
node js/bin/iconomics.js vat-return --period 2026-03 --in data/raw --out output/
```

Same subcommands, same flags, same exit codes, same stdout summary format. This is what
keeps the skill layer thin — a skill names a subcommand, not a language. Which runtime
executes it is set once in `config/runtime.yaml` (`python` or `node`), so the four skills
are written once and work for either audience.

**2. One set of golden files.** `data/expected/` is not per-language. Both implementations
are tested against the same expected workbooks. Neither gets to be the reference.

**3. A parity test.** `tests/test_parity.py` runs both implementations over every sample
input and diffs the resulting workbooks cell by cell, comparing values rather than file
bytes. Any divergence in figures, row counts, or exception classification fails the build.
This is the load-bearing mechanism; the other two are how it stays cheap to run.

**Library choices, and why they differ from the Python.**

| Concern | Python | JavaScript | Note |
|---|---|---|---|
| Spreadsheet I/O | openpyxl | exceljs | Both write formatted multi-sheet output with live formulas. SheetJS was rejected: the community edition's styling support is too limited for presentation-ready statements. |
| Money | `decimal.Decimal` | decimal.js | Chosen over integer-minor-units and big.js specifically because decimal.js supports explicit rounding modes matching Python's, so `ROUND_HALF_UP` means the same thing in both. Parity is a library-selection criterion here, not an afterthought. |
| Tabular manipulation | pandas | plain arrays of objects | No JS equivalent of pandas is worth the dependency at this data scale. The JS implementation is more explicit and, for a JS-reading audience, easier to follow. |

The module boundaries described below are identical across both languages — `workbook`,
`money`, `vat`, `reconcile`, `statements`, `coa` exist in both, with the same
responsibilities and the same interfaces adapted to each language's idiom. The contracts
are specified once because they are genuinely one design.

**Setup cost to the reader.** Each implementation stands alone. An accountant who only
wants the tool runs `pip install -e py/` and never learns that the JavaScript exists. The
README presents Python first for that reason, with the JavaScript as an equal alternative
rather than an appendix.

### Module contracts

Each module has one purpose, a narrow interface, and declared dependencies. The contracts
below describe both implementations — module names are given in Python form for brevity,
and the JavaScript modules mirror them exactly (`workbook.js`, `money.js`, and so on). The
`Depends on` lines name the Python libraries; substitute the JavaScript equivalents from the
table above.

**`workbook.py`** — the only module that touches `.xlsx`.
- *Does:* loads a spreadsheet into a canonical `DataFrame`; writes formatted multi-sheet
  output with live formulas.
- *Interface:* `load(path, profile) -> Ledger`, `write(path, sheets: dict[str, Sheet])`.
- *Key responsibility:* header normalisation. Maps `Дата`/`дата`/`Date`/`ДАТА` → `date`,
  `Контрагент`/`Партньор` → `counterparty`, and so on, via a mapping in
  `config/headers.yaml`. Unmapped columns are preserved, never dropped.
- *Boundary rule:* converts every monetary column to `Decimal` on load. No `float` money
  crosses this boundary inward, and none crosses outward.
- *Depends on:* openpyxl, pandas, `money.py`.

**`money.py`** — money arithmetic and currency.
- *Does:* `Money` type wrapping `Decimal` with a currency tag; BGN⇄EUR conversion at the
  fixed 1.95583 rate with the official rounding rule (half-up to 2 decimals);
  period-aware currency defaulting (before 2026-01-01 → BGN, after → EUR).
- *Interface:* `Money(amount, currency)`, `.to_eur()`, `.to_bgn()`, `restate(series, target)`.
- *Invariant:* conversion is never chained. Always convert from the original recorded
  amount, so BGN→EUR→BGN cannot drift.
- *Depends on:* stdlib `decimal` only.

**`vat.py`** — VAT classification and computation.
- *Does:* two-layer rate resolution. An EU core (standard / reduced / zero, reverse charge,
  intra-community supply and acquisition) and a Bulgarian layer supplying the actual rates
  and the journal/declaration field layout.
- *Interface:* `classify(row) -> VatTreatment`, `build_return(ledger, period) -> VatReturn`.
- *`VatReturn` contains:* sales journal rows, purchase journal rows, declaration totals,
  VIES rows. Constructed so declaration totals are *derived from* the journals rather than
  computed in parallel — they cannot disagree.
- *Depends on:* `money.py`, `config/vat-rates.yaml`.

**`reconcile.py`** — bank statement ↔ ledger matching.
- *Does:* tiered matching. Exact (amount + date + reference), then fuzzy (amount within
  tolerance, date within a window, counterparty similarity), then unmatched.
- *Interface:* `reconcile(statement, ledger, tolerance) -> Reconciliation`.
- *Output:* matched pairs with a confidence tier, plus `Exceptions` rows carrying a reason.
  Fuzzy matches are never presented as confirmed; they are proposals for human review.
- *Depends on:* `money.py`.

**`statements.py`** — trial balance → financial statements.
- *Does:* rolls a trial balance into P&L, balance sheet, and cash-flow statement, with
  prior-period comparatives restated to EUR.
- *Interface:* `build(trial_balance, prior=None) -> Statements`.
- *Invariant:* asserts debits equal credits before producing output, and that the balance
  sheet balances after. Refuses to emit an unbalanced statement.
- *Depends on:* `coa.py`, `money.py`.

**`coa.py`** — chart of accounts.
- *Does:* loads account codes and their statement mapping from `config/coa.yaml`;
  resolves an account code to its statement line.
- *Interface:* `Coa.load(path)`, `.line_for(code)`, `.validate(codes)`.
- *Depends on:* `config/coa.yaml`.

## Data model

One canonical shape, so every module speaks the same language:

| Field | Type | Notes |
|---|---|---|
| `source_row` | int | 1-indexed row in the original file. Never lost. |
| `date` | date | Parsed from any of the messy input formats. |
| `counterparty` | str | Normalised: whitespace collapsed, case preserved. |
| `vat_number` | str \| None | Validated shape only, not existence. |
| `description` | str | |
| `amount_net` | Money | |
| `vat_amount` | Money | |
| `vat_rate` | Decimal | |
| `account` | str \| None | Chart-of-accounts code. |
| `currency` | str | `BGN` or `EUR`, as originally recorded. |

`source_row` is the spine of the audit trail. Every output row in every workflow carries
it, so any figure can be traced back to the cell it came from. This is the single most
important property for an accountant's trust in the tool.

## The four skills

Each skill is a `SKILL.md` with a description that triggers on natural phrasing, and a
short procedure. They are thin by design — the logic is in the library.

**`ledger-cleanup`** — *"clean up this export", "these dates are a mess"*
Loads a raw file, reports what it found wrong (mixed date formats, numbers stored as text,
merged cells, trailing-space duplicate vendors, mixed BGN/EUR), asks the user to confirm
ambiguous calls, writes a clean workbook plus a change log sheet showing every
transformation applied and to which row.

**`bank-reconciliation`** — *"reconcile the January bank statement"*
Loads statement and ledger, runs tiered matching, presents a summary (matched / proposed /
unmatched counts and values), writes a workbook with `Matched`, `Proposed`, `Exceptions`
sheets. Handles the January 2026 case where the statement is in EUR and the ledger opens
in BGN.

**`bg-vat-return`** — *"prepare the VAT return for March"*
Classifies every row, builds the sales and purchase journals, derives the declaration,
extracts VIES rows. Writes one workbook with those four sheets and a reconciliation sheet
proving journal totals tie to the declaration. Flags rows it could not classify rather
than guessing.

**`financial-statements`** — *"produce the P&L and balance sheet for H1"*
Validates the trial balance, rolls it up via the chart of accounts, restates prior-year
BGN comparatives to EUR, writes P&L / balance sheet / cash flow with live formulas so the
accountant can trace and adjust in Excel.

## Sample data

`data/raw/` is deliberately hostile, because that is what real exports look like:

- Cyrillic headers, inconsistent between files (`Контрагент` in one, `Партньор` in another)
- Dates as `01.02.2026`, `2026-02-01`, `1-Feb-26`, and Excel serial numbers, in one column
- Amounts as text with a comma decimal separator and a thousands space: `"1 234,56"`
- Duplicate vendors differing only by trailing whitespace or `ООД` vs `ООД.`
- A January 2026 file mixing BGN and EUR rows
- Prior-year (2025) figures entirely in BGN, needing restatement
- A handful of genuinely ambiguous rows with no correct automated answer, to demonstrate
  that the tool asks rather than guesses

`data/expected/` holds golden outputs for each workflow.

## README

The README is a deliverable, not documentation. Structure:

1. **What this is** — one paragraph: a real accounting toolkit, built as a demo of working
   with Claude Code.
2. **The 2026 problem** — the euro transition framing. Establishes immediate relevance.
3. **Setup** — three commands.
4. **Four walkthroughs** — one per workflow. Each shows the actual sentence typed to
   Claude, what Claude does, and the resulting spreadsheet. This is the persuasive core:
   the reader sees plain Bulgarian-accountant English producing a filed-ready workbook.
5. **How to point it at your own books** — edit `config/`, drop files in `data/raw/`.
6. **How the skills work** — brief, for the curious reader who wants to write their own.

## Testing

- **Golden-file tests** — each workflow run against `data/raw/` and compared to
  `data/expected/`. Run for both implementations against the same expected files.
- **Parity tests** — both implementations run over every sample input, outputs diffed cell
  by cell on values. Any divergence fails the build. This is what makes two
  implementations safe to maintain.
- **Invariant tests** — debits equal credits; balance sheet balances; VAT journal totals
  equal declaration totals; BGN→EUR→BGN round-trips within one cent. Written twice, once
  per language, because they test the arithmetic rather than the plumbing.
- **Boundary tests** — no float money crosses the `workbook` boundary in either language.
  In Python, assert `Decimal`. In JavaScript, assert `Decimal` instances from decimal.js
  and reject bare `number` in monetary fields.
- **Messy-input unit tests** — each date format, each number format, each duplicate-vendor
  variant, tested individually so a parsing failure names the exact case.

Commands:

```
pytest                                          # Python suite
pytest tests/test_vat.py::test_reverse_charge    # single Python test
npm --prefix js test                            # JavaScript suite
npm --prefix js test -- -t "reverse charge"      # single JavaScript test
pytest tests/test_parity.py                     # cross-language parity
```

## Error handling

The governing rule: **never silently drop or silently guess.**

- Unparseable input → row goes to `Exceptions` with a reason, processing continues.
- Ambiguous classification → surfaced to the user for a decision, not defaulted.
- Structural failure (unbalanced trial balance, missing required column) → hard error
  before any output is written. A half-correct financial statement is worse than none.
- Every exception row carries `source_row`, so the accountant can open the original file
  and look at it.

## Config

- `config/vat-rates.yaml` — rates with effective dates, and the treatment rules.
- `config/coa.yaml` — chart of accounts and statement mapping.
- `config/headers.yaml` — input header aliases → canonical field names.

Rules live here so the accountant can maintain them without touching Python.

## Known gap: the chart of accounts

Research on 2026-07-26 confirmed that Bulgarian law requires companies to use a statutory
chart of accounts, and that non-PIE entities apply National Accounting Standards issued by
the Ministry of Finance ([ICAEW](https://www.icaew.com/technical/by-country/europe/bulgaria/accounting-in-bulgaria),
[Accountancy Act](https://www.ides.bg/media/2143/accountancy_act.pdf)). It did **not**
yield a citable listing of the statutory account groups from a source solid enough to
hardcode.

Therefore `config/coa.yaml` ships with plausible account codes explicitly marked
`# ILLUSTRATIVE — replace with your firm's сметкоплан`, and `coa.py` treats the chart as
data. Replacing it is a one-file edit. This is the correct design regardless — different
firms extend the statutory chart with their own sub-accounts — but it is being chosen here
partly because the authoritative codes are unverified. Worth confirming with the friend,
who will simply know the right answer.

## Step 2 preview

SAF-T export, as its own spec. Bulgaria began mandatory SAF-T in January 2026 for large
enterprises (2023 net revenue over BGN 300m or collected taxes over BGN 3.5m), phasing
down to micro-enterprises by 2030, filed monthly by the 14th with annual fixed-asset data,
under a six-month penalty grace period
([Sovos](https://sovos.com/regulatory-updates/trr/bulgaria-mandatory-saf-t-reporting-from-2026/),
[Taxually](https://www.taxually.com/blog/bulgaria-introduces-mandatory-saf-t-reporting-starting-2026)).

It is deliberately deferred: it is an XML schema-conformance problem, largely disjoint from
the spreadsheet work above, and it would have doubled this spec while making the demo
harder to follow. The canonical data model defined here is the natural input to it, so
step 1 is a genuine foundation for step 2 rather than a detour.
