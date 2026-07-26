---
name: bg-vat-return
description: Use when preparing a Bulgarian monthly VAT return — the sales and purchase journals, the declaration totals, and the VIES list for intra-EU B2B. Triggers on "prepare the VAT return", "ДДС декларация", "дневник продажби", "VIES declaration", "how much VAT do we owe".
---

# Bulgarian VAT Return

Builds the four documents a Bulgarian monthly filing consists of: the sales
journal, the purchase journal, the declaration, and the VIES declaration for
intra-EU B2B supplies.

Read `config/runtime.yaml` for the runtime. Both implementations exist and
produce identical output — `tools/check_parity.py` verifies it cell by cell.

```
python -m iconomics vat-return --in <journal.xlsx> --out output/ [--currency EUR]
node js/bin/iconomics.js vat-return --in <journal.xlsx> --out output/
```

## What the input must contain

Beyond the usual ledger columns, a VAT return needs two things:

- **A VAT rate per row** (`Ставка`, `ДДС %`). Without it the row cannot be
  classified and goes to `Exceptions`.
- **A direction** — sale or purchase (`Вид документ`, `Посока`). Values like
  `Продажба`, `Приход`, `Фактура издадена` all read as a sale; `Покупка`,
  `Разход`, `Фактура получена` as a purchase.

**If there is no direction column**, direction is *inferred* from the account
code: a 7xx account is revenue, so a sale; anything else a purchase. This is an
inference, not a reading. Say so when it happens, because a misdirected row lands
in the wrong journal and the return will be wrong in a way that ties internally
and so looks correct.

## How classification works

Data-driven, never guessed from the description text:

| Rate | Counterparty VAT number | Treatment |
|---|---|---|
| 20% | any | Облагаема доставка 20% |
| 9% | any | Облагаема доставка 9% |
| 0% | starts `BG`, or absent | **Нулева ставка / освободена — flagged for review** |
| 0% | non-BG EU number, sale | Вътреобщностна доставка → also appears in VIES |
| 0% | non-BG EU number, purchase | Вътреобщностно придобиване (reverse charge) |
| anything else | — | **Unclassified → Exceptions** |

The 0%-domestic case is deliberately flagged rather than assigned. Zero-rated and
exempt are different things with different consequences, and the rate alone does
not distinguish them.

## The declaration cannot disagree with the journals

The declaration totals are **derived from** the journal rows, not computed
alongside them. A return whose declaration does not tie to its journals gets
rejected, and the usual cause is two independent computations drifting apart.
Here there is only one computation, and the output carries a `Reconciliation`
sheet proving it — check that sheet says `yes` on both rows and mention it.

## ⚠ The declaration is not the official form

The справка-декларация has numbered cells. A citable listing of that numbering
was **not found** in accessible sources on 2026-07-26 — only confirmation that
the return comprises a declaration plus the two journals, filed by the 14th.

So the `Декларация` sheet uses **descriptive line labels**, and its `Line` column
is populated from `declaration_cells` in `config/vat-rates.yaml`, which ships
**empty on purpose**. A wrong cell number on a filed return is worse than a
missing one.

**Always state this.** The output is a working paper that gets the figures right;
mapping them onto the official form is a step the accountant still does. Do not
imply the file can be filed as-is. If the user has the НАП form specification,
offer to fill in `declaration_cells` — that is a one-file change.

## Procedure

1. Run the command on the journal file.
2. **Report the exceptions first** — unclassified rows and undetermined
   directions. These make the return wrong if ignored.
3. Report the headline figures: output VAT, input VAT, and the net payable or
   refundable. Name which it is; a negative net is a refund position.
4. Confirm the `Reconciliation` sheet ties.
5. State the official-cell caveat above.
6. Note the filing deadline — the **14th of the following month** per
   `config/vat-rates.yaml`. Re-verify it if the filing is imminent; it is a
   regulatory fact with a research date, not a constant.

## Do not

- Do not compute a VAT figure yourself to "check" the tool. Read the
  `Reconciliation` sheet.
- Do not treat a missing VAT number as intra-EU. No number means domestic here.
- Do not advise on whether input VAT is deductible. The tool totals what is in the
  books; deductibility is a judgement the accountant makes.
