---
name: exception-triage
description: Use after a cleanup run to work through the rows the toolkit set aside — unreadable amounts, missing dates, unknown columns. Triggers on "what went wrong", "fix the exceptions", "why were these rows rejected", "оправи грешките".
---

# Exception Triage

A cleanup run splits the ledger in two: rows the toolkit could read, and rows it
refused to guess at. This skill works through the second group with the user.

The goal is not to make the exceptions disappear. It is to get a decision from
the person who is allowed to make one, and to get that decision into the source
data or the config where it belongs.

## Procedure

1. **Open the `Exceptions` sheet** of the cleanup output. Each row has the source
   row number, the field, the raw value, and the reason.
2. **Group by reason**, not by row. Twenty rows failing for one cause is one
   conversation; twenty separate conversations wastes the user's time.
3. **For each group, propose a specific fix** and say where it goes:
   - a recurring header the toolkit does not recognize → add an alias to
     `config/headers.yaml`, then re-run. This is the fix that pays off, because
     it then works for every future export from the same system.
   - a genuinely unreadable value in one cell → the user corrects the source
     file, or confirms the row should be excluded
   - a placeholder like `n/a`, `—`, or a blank → ask what it means. It is
     usually either zero or "not yet known", and those are not the same thing.
4. **Re-run after config changes** and confirm the exception count dropped.
5. **Never silently write a value into `data/raw/`.** If a source file needs
   correcting, either the user does it, or you do it only after they have said
   exactly what the value should be.

## Reading the reasons

| Reason | What it means | Usual fix |
|---|---|---|
| `empty cell` | The field is blank | Ask whether the row is incomplete or the value is genuinely zero |
| `cannot read amount from '…'` | Text where a number belongs | Ask what the placeholder means |
| `ambiguous separators in '…'` | More than one comma or dot, or unexpected digit grouping | Ask the user to confirm the intended figure |
| `cannot read date from '…'` | An unrecognized date format | If it recurs, the format is worth supporting — say so |
| `invalid date …` | A real-looking date that does not exist, e.g. 32 January | A typo in the source |

## A column the toolkit ignored is not an error

Unmapped columns are preserved, not dropped, and they appear in
`unmapped_headers` rather than in `Exceptions`. If the user asks why a column is
missing from the `Clean` sheet, the answer is that it was carried through but not
mapped to a canonical field — and if it holds something the toolkit should
understand, add it to `config/headers.yaml`.

## Duplicates are not exceptions either

Two identical rows are kept as two rows. Cleanup merges vendor *spellings*, not
transactions — a genuine double entry and a legitimate repeated charge look the
same, and only the accountant can tell them apart. If you notice identical rows,
mention them as something to check; do not remove either one.

## Tone

Exceptions are the tool's most trustworthy output. Present them that way. A run
reporting two exceptions out of fourteen rows has told the accountant exactly
where to spend their attention, which is worth more than a run that quietly
produced fourteen confident-looking rows, two of them wrong.
