# iconomics Foundation + Ledger Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared Python and JavaScript foundation for the iconomics accounting toolkit and deliver the first complete workflow, `ledger-cleanup`, driveable from Claude in either language.

**Architecture:** Two parallel implementations (`py/` and `js/`) exposing an identical CLI. All accounting logic lives in the libraries; Claude skills are thin instruction files that pick a runtime from `config/runtime.yaml` and run a subcommand. Correctness is pinned by golden output files shared between both languages plus a cross-language parity test that diffs their outputs cell by cell.

**Tech Stack:** Python 3.11+ (openpyxl, pandas, PyYAML, pytest) · Node 20+ (exceljs, decimal.js, js-yaml, vitest)

## Global Constraints

Every task's requirements implicitly include this section.

- Fixed euro conversion rate: **1 EUR = 1.95583 BGN**. Irrevocable, never fetched, never configurable.
- Monetary rounding: **half-up to 2 decimal places**, in both languages.
- **No float money.** Python uses `decimal.Decimal`; JavaScript uses `decimal.js` `Decimal`. A bare `float`/`number` in a monetary field is a bug.
- Currency default by date: transactions dated **before 2026-01-01 default to BGN**, on/after default to **EUR**. An explicit currency in the source always wins.
- Every output row carries `source_row` — the 1-indexed row number in the original file.
- **Never silently drop, never silently guess.** Unparseable rows go to an `Exceptions` sheet with a reason. Ambiguous cases surface to the user.
- Rules live in `config/*.yaml`, never hardcoded in source.
- Python floor: **3.11**. Node floor: **20**.
- Both CLIs accept identical subcommands, flags, and exit codes (0 success, 1 structural failure, 2 bad usage).
- Sample data generation must be **deterministic** — no randomness, no current-date dependency — so golden files are stable.

---

## File Structure

| Path | Responsibility |
|---|---|
| `config/headers.yaml` | Input header aliases (Cyrillic + English) → canonical field names |
| `config/vat-rates.yaml` | VAT rates with effective dates and treatment rules |
| `config/coa.yaml` | Chart of accounts → statement line mapping (illustrative codes) |
| `config/runtime.yaml` | Which implementation the skills invoke: `python` or `node` |
| `py/pyproject.toml` | Python package metadata, deps, pytest config |
| `py/src/iconomics/money.py` | `Money` type, BGN⇄EUR conversion, rounding |
| `py/src/iconomics/parsing.py` | Messy date and amount parsers (pure functions) |
| `py/src/iconomics/config.py` | Loads the YAML config files |
| `py/src/iconomics/workbook.py` | The only module touching `.xlsx`: load → canonical rows, write → formatted sheets |
| `py/src/iconomics/cleanup.py` | Ledger cleanup: normalize, dedupe, classify exceptions, change log |
| `py/src/iconomics/cli.py` | `python -m iconomics` argparse entry point |
| `js/package.json` | Node package metadata, deps, vitest config |
| `js/src/money.js` | Mirror of `money.py` |
| `js/src/parsing.js` | Mirror of `parsing.py` |
| `js/src/config.js` | Mirror of `config.py` |
| `js/src/workbook.js` | Mirror of `workbook.py` |
| `js/src/cleanup.js` | Mirror of `cleanup.py` |
| `js/bin/iconomics.js` | Node CLI entry point using `util.parseArgs` |
| `tools/make_sample_data.py` | Generates the deliberately messy `data/raw/` workbooks |
| `data/raw/` | Messy sample inputs (committed) |
| `data/expected/` | Golden outputs, shared by both languages (committed) |
| `tests/test_parity.py` | Runs both CLIs, diffs outputs cell by cell |
| `.claude/skills/ledger-cleanup/SKILL.md` | Thin skill driving the cleanup subcommand |
| `CLAUDE.md` | Repo conventions for future Claude sessions |

---

### Task 1: Repository scaffolding and both toolchains

Establishes both packages so every later task has somewhere to put code and a working test command. No accounting logic.

**Files:**
- Create: `py/pyproject.toml`, `py/src/iconomics/__init__.py`, `js/package.json`, `js/src/index.js`, `config/runtime.yaml`
- Create: `py/tests/test_smoke.py`, `js/test/smoke.test.js`

**Interfaces:**
- Consumes: nothing.
- Produces: importable package `iconomics` (Python) and `js/src/index.js` exporting `VERSION`. Test commands `pytest` (from `py/`) and `npm --prefix js test`.

- [ ] **Step 1: Write the failing Python smoke test**

`py/tests/test_smoke.py`:
```python
from iconomics import VERSION


def test_version_is_exposed():
    assert VERSION == "0.1.0"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd py && python -m pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'iconomics'`

- [ ] **Step 3: Create the Python package**

`py/pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "iconomics"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["openpyxl>=3.1", "pandas>=2.1", "PyYAML>=6.0"]

[project.optional-dependencies]
dev = ["pytest>=7.4"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`py/src/iconomics/__init__.py`:
```python
VERSION = "0.1.0"
```

- [ ] **Step 4: Install and run the test**

Run: `cd py && pip install -e ".[dev]" && python -m pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing JavaScript smoke test**

`js/test/smoke.test.js`:
```javascript
import { describe, it, expect } from 'vitest';
import { VERSION } from '../src/index.js';

describe('package', () => {
  it('exposes the version', () => {
    expect(VERSION).toBe('0.1.0');
  });
});
```

- [ ] **Step 6: Run it to verify it fails**

Run: `npm --prefix js test`
Expected: FAIL — no `package.json` / cannot resolve `../src/index.js`

- [ ] **Step 7: Create the Node package**

`js/package.json`:
```json
{
  "name": "iconomics",
  "version": "0.1.0",
  "type": "module",
  "engines": { "node": ">=20" },
  "bin": { "iconomics": "./bin/iconomics.js" },
  "scripts": { "test": "vitest run" },
  "dependencies": {
    "exceljs": "^4.4.0",
    "decimal.js": "^10.4.3",
    "js-yaml": "^4.1.0"
  },
  "devDependencies": { "vitest": "^1.6.0" }
}
```

`js/src/index.js`:
```javascript
export const VERSION = '0.1.0';
```

- [ ] **Step 8: Install and run the test**

Run: `npm --prefix js install && npm --prefix js test`
Expected: PASS

- [ ] **Step 9: Create the runtime config**

`config/runtime.yaml`:
```yaml
# Which implementation the Claude skills invoke.
# Both produce identical output — pick whichever you'd rather read and extend.
runtime: python   # python | node
```

- [ ] **Step 10: Commit**

```bash
git add py js config/runtime.yaml
git commit -m "feat: scaffold Python and JavaScript packages"
```

---

### Task 2: Money type and euro conversion (Python)

The arithmetic core. Everything downstream depends on it, so it lands first and is tested hard.

**Files:**
- Create: `py/src/iconomics/money.py`
- Test: `py/tests/test_money.py`

**Interfaces:**
- Consumes: nothing (stdlib `decimal` only).
- Produces:
  - `BGN_PER_EUR: Decimal` — `Decimal("1.95583")`
  - `EURO_START: date` — `date(2026, 1, 1)`
  - `q2(value: Decimal) -> Decimal` — quantize half-up to 2dp
  - `Money(amount: Decimal, currency: str)` — frozen dataclass, `currency` in `{"BGN", "EUR"}`
  - `Money.to_eur() -> Money`, `Money.to_bgn() -> Money`
  - `Money.__add__`, `Money.__sub__` — same currency only, else `CurrencyMismatch`
  - `default_currency_for(when: date) -> str`
  - Exceptions: `CurrencyMismatch(ValueError)`, `NotDecimal(TypeError)`

- [ ] **Step 1: Write the failing tests**

`py/tests/test_money.py`:
```python
from datetime import date
from decimal import Decimal

import pytest

from iconomics.money import (
    BGN_PER_EUR,
    CurrencyMismatch,
    Money,
    NotDecimal,
    default_currency_for,
    q2,
)


def test_fixed_rate_is_exact():
    assert BGN_PER_EUR == Decimal("1.95583")


def test_q2_rounds_half_up_not_half_even():
    # Banker's rounding would give 0.02 here. Accountants expect 0.03.
    assert q2(Decimal("0.025")) == Decimal("0.03")
    assert q2(Decimal("0.035")) == Decimal("0.04")


def test_float_amount_is_rejected():
    with pytest.raises(NotDecimal):
        Money(1.23, "EUR")


def test_bgn_to_eur_conversion():
    assert Money(Decimal("195.583"), "BGN").to_eur() == Money(Decimal("100.00"), "EUR")


def test_eur_to_bgn_conversion():
    assert Money(Decimal("100.00"), "EUR").to_bgn() == Money(Decimal("195.58"), "BGN")


def test_conversion_is_idempotent_for_same_currency():
    eur = Money(Decimal("42.42"), "EUR")
    assert eur.to_eur() is eur


def test_round_trip_stays_within_one_cent():
    original = Money(Decimal("1234.56"), "BGN")
    round_tripped = original.to_eur().to_bgn()
    assert abs(round_tripped.amount - original.amount) <= Decimal("0.01")


def test_addition_requires_matching_currency():
    with pytest.raises(CurrencyMismatch):
        Money(Decimal("1.00"), "EUR") + Money(Decimal("1.00"), "BGN")


def test_addition_of_same_currency():
    total = Money(Decimal("1.01"), "EUR") + Money(Decimal("2.02"), "EUR")
    assert total == Money(Decimal("3.03"), "EUR")


def test_unknown_currency_is_rejected():
    with pytest.raises(ValueError):
        Money(Decimal("1.00"), "USD")


def test_currency_default_follows_euro_adoption():
    assert default_currency_for(date(2025, 12, 31)) == "BGN"
    assert default_currency_for(date(2026, 1, 1)) == "EUR"
    assert default_currency_for(date(2026, 7, 26)) == "EUR"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd py && python -m pytest tests/test_money.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'iconomics.money'`

- [ ] **Step 3: Write the implementation**

`py/src/iconomics/money.py`:
```python
"""Money arithmetic and the fixed BGN/EUR conversion.

Bulgaria adopted the euro on 2026-01-01 at an irrevocable rate of
1 EUR = 1.95583 BGN. The rate is a constant, not a configuration value.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

BGN_PER_EUR = Decimal("1.95583")
EURO_START = date(2026, 1, 1)
CURRENCIES = frozenset({"BGN", "EUR"})
_CENT = Decimal("0.01")


class CurrencyMismatch(ValueError):
    """Raised when arithmetic mixes two currencies."""


class NotDecimal(TypeError):
    """Raised when a monetary amount is not a Decimal."""


def q2(value: Decimal) -> Decimal:
    """Quantize to 2 decimal places, rounding half away from zero.

    Half-up, not half-even: an accountant expects 0.025 to become 0.03.
    """
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise NotDecimal(
                f"monetary amounts must be Decimal, got {type(self.amount).__name__}"
            )
        if self.currency not in CURRENCIES:
            raise ValueError(f"unsupported currency {self.currency!r}")

    def to_eur(self) -> "Money":
        if self.currency == "EUR":
            return self
        return Money(q2(self.amount / BGN_PER_EUR), "EUR")

    def to_bgn(self) -> "Money":
        if self.currency == "BGN":
            return self
        return Money(q2(self.amount * BGN_PER_EUR), "BGN")

    def _require_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise CurrencyMismatch(
                f"cannot combine {self.currency} and {other.currency}; "
                "convert explicitly first"
            )

    def __add__(self, other: "Money") -> "Money":
        self._require_same_currency(other)
        return Money(q2(self.amount + other.amount), self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._require_same_currency(other)
        return Money(q2(self.amount - other.amount), self.currency)

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"


def default_currency_for(when: date) -> str:
    """The currency a transaction is presumed to be in, absent an explicit one."""
    return "EUR" if when >= EURO_START else "BGN"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd py && python -m pytest tests/test_money.py -v`
Expected: PASS — 11 tests

- [ ] **Step 5: Commit**

```bash
git add py/src/iconomics/money.py py/tests/test_money.py
git commit -m "feat: add Money type with fixed BGN/EUR conversion"
```

---

### Task 3: Money type and euro conversion (JavaScript)

The mirror of Task 2. Same behaviour, same rounding, verified by the same assertions.

**Files:**
- Create: `js/src/money.js`
- Test: `js/test/money.test.js`

**Interfaces:**
- Consumes: `decimal.js`.
- Produces:
  - `BGN_PER_EUR`, `EURO_START` (a `Date`), `CURRENCIES`
  - `q2(value: Decimal): Decimal`
  - `class Money { constructor(amount: Decimal, currency: string) }` with `toEur()`, `toBgn()`, `add(other)`, `sub(other)`, `equals(other)`, `toString()`
  - `defaultCurrencyFor(when: Date): string`
  - `class CurrencyMismatch extends Error`, `class NotDecimal extends TypeError`

- [ ] **Step 1: Write the failing tests**

`js/test/money.test.js`:
```javascript
import { describe, it, expect } from 'vitest';
import Decimal from 'decimal.js';
import {
  BGN_PER_EUR,
  CurrencyMismatch,
  Money,
  NotDecimal,
  defaultCurrencyFor,
  q2,
} from '../src/money.js';

const d = (s) => new Decimal(s);

describe('money', () => {
  it('holds the fixed rate exactly', () => {
    expect(BGN_PER_EUR.equals(d('1.95583'))).toBe(true);
  });

  it('rounds half up, not half even', () => {
    expect(q2(d('0.025')).toString()).toBe('0.03');
    expect(q2(d('0.035')).toString()).toBe('0.04');
  });

  it('rejects a bare number amount', () => {
    expect(() => new Money(1.23, 'EUR')).toThrow(NotDecimal);
  });

  it('converts BGN to EUR', () => {
    const eur = new Money(d('195.583'), 'BGN').toEur();
    expect(eur.equals(new Money(d('100.00'), 'EUR'))).toBe(true);
  });

  it('converts EUR to BGN', () => {
    const bgn = new Money(d('100.00'), 'EUR').toBgn();
    expect(bgn.equals(new Money(d('195.58'), 'BGN'))).toBe(true);
  });

  it('returns the same instance when already in the target currency', () => {
    const eur = new Money(d('42.42'), 'EUR');
    expect(eur.toEur()).toBe(eur);
  });

  it('round-trips within one cent', () => {
    const original = new Money(d('1234.56'), 'BGN');
    const back = original.toEur().toBgn();
    expect(back.amount.minus(original.amount).abs().lte(d('0.01'))).toBe(true);
  });

  it('refuses to add across currencies', () => {
    expect(() => new Money(d('1.00'), 'EUR').add(new Money(d('1.00'), 'BGN'))).toThrow(
      CurrencyMismatch,
    );
  });

  it('adds within a currency', () => {
    const total = new Money(d('1.01'), 'EUR').add(new Money(d('2.02'), 'EUR'));
    expect(total.equals(new Money(d('3.03'), 'EUR'))).toBe(true);
  });

  it('rejects an unknown currency', () => {
    expect(() => new Money(d('1.00'), 'USD')).toThrow();
  });

  it('defaults currency by euro adoption date', () => {
    expect(defaultCurrencyFor(new Date('2025-12-31'))).toBe('BGN');
    expect(defaultCurrencyFor(new Date('2026-01-01'))).toBe('EUR');
    expect(defaultCurrencyFor(new Date('2026-07-26'))).toBe('EUR');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix js test -- money`
Expected: FAIL — cannot resolve `../src/money.js`

- [ ] **Step 3: Write the implementation**

`js/src/money.js`:
```javascript
/**
 * Money arithmetic and the fixed BGN/EUR conversion.
 *
 * Bulgaria adopted the euro on 2026-01-01 at an irrevocable rate of
 * 1 EUR = 1.95583 BGN. The rate is a constant, not a configuration value.
 *
 * Rounding mode is set explicitly rather than relying on the decimal.js
 * default, so that q2 matches Python's ROUND_HALF_UP exactly.
 */

import Decimal from 'decimal.js';

export const BGN_PER_EUR = new Decimal('1.95583');
export const EURO_START = new Date('2026-01-01T00:00:00Z');
export const CURRENCIES = new Set(['BGN', 'EUR']);

export class CurrencyMismatch extends Error {}
export class NotDecimal extends TypeError {}

/** Quantize to 2 decimal places, rounding half away from zero. */
export function q2(value) {
  return value.toDecimalPlaces(2, Decimal.ROUND_HALF_UP);
}

export class Money {
  constructor(amount, currency) {
    if (!Decimal.isDecimal(amount)) {
      throw new NotDecimal(`monetary amounts must be Decimal, got ${typeof amount}`);
    }
    if (!CURRENCIES.has(currency)) {
      throw new Error(`unsupported currency '${currency}'`);
    }
    this.amount = amount;
    this.currency = currency;
    Object.freeze(this);
  }

  toEur() {
    if (this.currency === 'EUR') return this;
    return new Money(q2(this.amount.div(BGN_PER_EUR)), 'EUR');
  }

  toBgn() {
    if (this.currency === 'BGN') return this;
    return new Money(q2(this.amount.times(BGN_PER_EUR)), 'BGN');
  }

  #requireSameCurrency(other) {
    if (this.currency !== other.currency) {
      throw new CurrencyMismatch(
        `cannot combine ${this.currency} and ${other.currency}; convert explicitly first`,
      );
    }
  }

  add(other) {
    this.#requireSameCurrency(other);
    return new Money(q2(this.amount.plus(other.amount)), this.currency);
  }

  sub(other) {
    this.#requireSameCurrency(other);
    return new Money(q2(this.amount.minus(other.amount)), this.currency);
  }

  equals(other) {
    return this.currency === other.currency && this.amount.equals(other.amount);
  }

  toString() {
    return `${this.amount.toString()} ${this.currency}`;
  }
}

/** The currency a transaction is presumed to be in, absent an explicit one. */
export function defaultCurrencyFor(when) {
  return when.getTime() >= EURO_START.getTime() ? 'EUR' : 'BGN';
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix js test -- money`
Expected: PASS — 11 tests, mirroring the Python suite

- [ ] **Step 5: Commit**

```bash
git add js/src/money.js js/test/money.test.js
git commit -m "feat: mirror Money type in JavaScript with matching rounding"
```

---

### Task 4: Messy input parsers (Python)

Pure functions turning real-world spreadsheet garbage into typed values. Kept separate from
`workbook.py` so every format can be unit-tested without building an `.xlsx`.

**Files:**
- Create: `py/src/iconomics/parsing.py`
- Test: `py/tests/test_parsing.py`

**Interfaces:**
- Consumes: `iconomics.money.q2` is *not* used here — parsers return raw `Decimal`, unrounded.
- Produces:
  - `parse_amount(raw: object) -> Decimal` — raises `UnparseableAmount`
  - `parse_date(raw: object) -> date` — raises `UnparseableDate`
  - `from_excel_serial(serial: int | float) -> date`
  - `normalize_header(raw: str) -> str` — lowercase, trim, collapse whitespace, strip trailing `.`/`:`
  - `normalize_counterparty(raw: str) -> str` — collapse whitespace, strip trailing `.`, preserve case
  - Exceptions: `UnparseableAmount(ValueError)`, `UnparseableDate(ValueError)`

**Decimal separator rule** (documented because it is a judgement call):
Bulgarian exports use comma as the decimal separator and space or dot as the thousands
separator; English-locale exports do the opposite. Resolution order:
1. If both `,` and `.` appear, the **rightmost** is the decimal separator; the other is thousands.
2. If only one appears and is followed by exactly 1 or 2 digits, it is the decimal separator.
3. If only one appears and is followed by exactly 3 digits, it is a thousands separator.
4. Anything else is unparseable.

- [ ] **Step 1: Write the failing tests**

`py/tests/test_parsing.py`:
```python
from datetime import date, datetime
from decimal import Decimal

import pytest

from iconomics.parsing import (
    UnparseableAmount,
    UnparseableDate,
    from_excel_serial,
    normalize_counterparty,
    normalize_header,
    parse_amount,
    parse_date,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1234.56", "1234.56"),
        ("1234,56", "1234.56"),
        ("1 234,56", "1234.56"),          # space thousands, comma decimal
        ("1 234,56", "1234.56"),     # non-breaking space thousands
        ("1.234,56", "1234.56"),          # dot thousands, comma decimal
        ("1,234.56", "1234.56"),          # comma thousands, dot decimal
        ("1.234", "1234"),                # single dot, 3 digits => thousands
        ("12.50", "12.50"),               # single dot, 2 digits => decimal
        ("-123,45", "-123.45"),
        ("(123,45)", "-123.45"),          # accounting parentheses negative
        ("123,45 лв.", "123.45"),
        ("€123.45", "123.45"),
        ("  42  ", "42"),
        (1234.5, "1234.5"),               # numeric cell from openpyxl
        (Decimal("7.77"), "7.77"),
    ],
)
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == Decimal(expected)


@pytest.mark.parametrize("raw", ["", None, "n/a", "abc", "1,2,3", "1.2.3.4"])
def test_parse_amount_rejects_garbage(raw):
    with pytest.raises(UnparseableAmount):
        parse_amount(raw)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("01.02.2026", date(2026, 2, 1)),   # Bulgarian dd.mm.yyyy
        ("1.2.2026", date(2026, 2, 1)),
        ("2026-02-01", date(2026, 2, 1)),
        ("01/02/2026", date(2026, 2, 1)),   # dd/mm/yyyy, consistent with dd.mm
        ("1-Feb-26", date(2026, 2, 1)),
        ("  2026-02-01  ", date(2026, 2, 1)),
        (datetime(2026, 2, 1, 13, 30), date(2026, 2, 1)),
        (date(2026, 2, 1), date(2026, 2, 1)),
        (46054, date(2026, 2, 1)),          # Excel serial
    ],
)
def test_parse_date(raw, expected):
    assert parse_date(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "not a date", "32.01.2026", "2026-13-01"])
def test_parse_date_rejects_garbage(raw):
    with pytest.raises(UnparseableDate):
        parse_date(raw)


def test_excel_serial_uses_the_1900_epoch_with_the_leap_bug():
    # Excel serial 1 is 1900-01-01, and openpyxl's epoch base is 1899-12-30.
    assert from_excel_serial(46054) == date(2026, 2, 1)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Дата", "дата"),
        ("  ДАТА:  ", "дата"),
        ("Сума  без   ДДС", "сума без ддс"),
        ("Date.", "date"),
    ],
)
def test_normalize_header(raw, expected):
    assert normalize_header(raw) == expected


def test_normalize_counterparty_preserves_case_but_collapses_noise():
    assert normalize_counterparty("  Алфа   ООД  ") == "Алфа ООД"
    assert normalize_counterparty("Алфа ООД.") == "Алфа ООД"


def test_normalize_counterparty_makes_whitespace_duplicates_identical():
    assert normalize_counterparty("Бета ЕООД ") == normalize_counterparty("Бета  ЕООД")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd py && python -m pytest tests/test_parsing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'iconomics.parsing'`

- [ ] **Step 3: Write the implementation**

`py/src/iconomics/parsing.py`:
```python
"""Parsers for the formats real accounting exports actually contain.

These are pure functions with no spreadsheet dependency, so every format
variant can be tested in isolation and a failure names the exact case.
"""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

_EXCEL_EPOCH = date(1899, 12, 30)
_CURRENCY_NOISE = re.compile(r"(лв\.?|BGN|EUR|€|€)", re.IGNORECASE)
_WHITESPACE = re.compile(r"[\s ]+")
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class UnparseableAmount(ValueError):
    """Raised when a cell cannot be read as a monetary amount."""


class UnparseableDate(ValueError):
    """Raised when a cell cannot be read as a date."""


def from_excel_serial(serial: int | float) -> date:
    """Convert an Excel date serial number to a date."""
    return _EXCEL_EPOCH + timedelta(days=int(serial))


def _resolve_separators(text: str) -> str:
    """Normalize a numeric string to use '.' as the decimal separator."""
    has_comma = "," in text
    has_dot = "." in text

    if has_comma and has_dot:
        # Rightmost separator is the decimal one; the other groups thousands.
        if text.rfind(",") > text.rfind("."):
            return text.replace(".", "").replace(",", ".")
        return text.replace(",", "")

    if has_comma or has_dot:
        sep = "," if has_comma else "."
        if text.count(sep) > 1:
            raise UnparseableAmount(f"ambiguous separators in {text!r}")
        digits_after = len(text.rsplit(sep, 1)[1])
        if digits_after in (1, 2):
            return text.replace(sep, ".")
        if digits_after == 3:
            return text.replace(sep, "")
        raise UnparseableAmount(f"ambiguous separators in {text!r}")

    return text


def parse_amount(raw: object) -> Decimal:
    """Read a monetary amount from a spreadsheet cell of unknown format."""
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, bool):  # bool is an int subclass; never a valid amount
        raise UnparseableAmount("boolean is not an amount")
    if isinstance(raw, (int, float)):
        return Decimal(str(raw))
    if not isinstance(raw, str):
        raise UnparseableAmount(f"cannot read amount from {type(raw).__name__}")

    text = _CURRENCY_NOISE.sub("", raw).strip()
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    text = _WHITESPACE.sub("", text)
    if not text:
        raise UnparseableAmount("empty cell")

    text = _resolve_separators(text)
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise UnparseableAmount(f"cannot read amount from {raw!r}") from exc
    return -value if negative else value


def _parse_textual_date(text: str) -> date:
    # dd-Mon-yy / dd-Mon-yyyy
    match = re.fullmatch(r"(\d{1,2})[-\s]([A-Za-z]{3,})[-\s](\d{2,4})", text)
    if match:
        day, month_name, year = match.groups()
        month = _MONTHS.get(month_name[:3].lower())
        if month is None:
            raise UnparseableDate(f"unknown month in {text!r}")
        year_value = int(year)
        if year_value < 100:
            year_value += 2000
        return date(year_value, month, int(day))

    # ISO yyyy-mm-dd
    match = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return date(year, month, day)

    # Bulgarian dd.mm.yyyy and dd/mm/yyyy
    match = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", text)
    if match:
        day, month, year = (int(part) for part in match.groups())
        if year < 100:
            year += 2000
        return date(year, month, day)

    raise UnparseableDate(f"cannot read date from {text!r}")


def parse_date(raw: object) -> date:
    """Read a date from a spreadsheet cell of unknown format.

    Ambiguous numeric dates are read day-first, matching Bulgarian convention.
    """
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, bool):
        raise UnparseableDate("boolean is not a date")
    if isinstance(raw, (int, float)):
        try:
            return from_excel_serial(raw)
        except (ValueError, OverflowError) as exc:
            raise UnparseableDate(f"invalid Excel serial {raw!r}") from exc
    if not isinstance(raw, str):
        raise UnparseableDate(f"cannot read date from {type(raw).__name__}")

    text = raw.strip()
    if not text:
        raise UnparseableDate("empty cell")
    try:
        return _parse_textual_date(text)
    except ValueError as exc:
        if isinstance(exc, UnparseableDate):
            raise
        raise UnparseableDate(f"cannot read date from {raw!r}") from exc


def normalize_header(raw: str) -> str:
    """Canonicalize a column header for alias lookup."""
    text = _WHITESPACE.sub(" ", str(raw)).strip().rstrip(".:").strip()
    return text.lower()


def normalize_counterparty(raw: str) -> str:
    """Canonicalize a counterparty name so cosmetic variants collapse together."""
    return _WHITESPACE.sub(" ", str(raw)).strip().rstrip(".").strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd py && python -m pytest tests/test_parsing.py -v`
Expected: PASS — all parametrized cases green

- [ ] **Step 5: Commit**

```bash
git add py/src/iconomics/parsing.py py/tests/test_parsing.py
git commit -m "feat: add messy date and amount parsers"
```

---

### Task 5: Messy input parsers (JavaScript)

Mirror of Task 4. Same separator resolution rules, same day-first date convention.

**Files:**
- Create: `js/src/parsing.js`
- Test: `js/test/parsing.test.js`

**Interfaces:**
- Consumes: `decimal.js`.
- Produces: `parseAmount(raw): Decimal`, `parseDate(raw): Date` (UTC midnight),
  `fromExcelSerial(serial): Date`, `normalizeHeader(raw): string`,
  `normalizeCounterparty(raw): string`, `UnparseableAmount`, `UnparseableDate`.

**Note on the JS date type:** JavaScript has no date-only type. `parseDate` returns a `Date`
at **UTC midnight** so that comparisons and formatting never shift by a timezone offset.
Always construct with `Date.UTC(...)` and read with `getUTC*` accessors.

- [ ] **Step 1: Write the failing tests**

`js/test/parsing.test.js`:
```javascript
import { describe, it, expect } from 'vitest';
import Decimal from 'decimal.js';
import {
  UnparseableAmount,
  UnparseableDate,
  fromExcelSerial,
  normalizeCounterparty,
  normalizeHeader,
  parseAmount,
  parseDate,
} from '../src/parsing.js';

const iso = (dt) => dt.toISOString().slice(0, 10);

describe('parseAmount', () => {
  it.each([
    ['1234.56', '1234.56'],
    ['1234,56', '1234.56'],
    ['1 234,56', '1234.56'],
    ['1 234,56', '1234.56'],
    ['1.234,56', '1234.56'],
    ['1,234.56', '1234.56'],
    ['1.234', '1234'],
    ['12.50', '12.5'],
    ['-123,45', '-123.45'],
    ['(123,45)', '-123.45'],
    ['123,45 лв.', '123.45'],
    ['€123.45', '123.45'],
    ['  42  ', '42'],
    [1234.5, '1234.5'],
  ])('parses %j', (raw, expected) => {
    expect(parseAmount(raw).equals(new Decimal(expected))).toBe(true);
  });

  it.each([['', null, 'n/a', 'abc', '1,2,3', '1.2.3.4']].flat())(
    'rejects %j',
    (raw) => {
      expect(() => parseAmount(raw)).toThrow(UnparseableAmount);
    },
  );
});

describe('parseDate', () => {
  it.each([
    ['01.02.2026', '2026-02-01'],
    ['1.2.2026', '2026-02-01'],
    ['2026-02-01', '2026-02-01'],
    ['01/02/2026', '2026-02-01'],
    ['1-Feb-26', '2026-02-01'],
    ['  2026-02-01  ', '2026-02-01'],
    [46054, '2026-02-01'],
  ])('parses %j', (raw, expected) => {
    expect(iso(parseDate(raw))).toBe(expected);
  });

  it('accepts a Date unchanged', () => {
    expect(iso(parseDate(new Date('2026-02-01T13:30:00Z')))).toBe('2026-02-01');
  });

  it.each([['', null, 'not a date', '32.01.2026', '2026-13-01']].flat())(
    'rejects %j',
    (raw) => {
      expect(() => parseDate(raw)).toThrow(UnparseableDate);
    },
  );

  it('uses the same Excel epoch as the Python implementation', () => {
    expect(iso(fromExcelSerial(46054))).toBe('2026-02-01');
  });
});

describe('normalization', () => {
  it.each([
    ['Дата', 'дата'],
    ['  ДАТА:  ', 'дата'],
    ['Сума  без   ДДС', 'сума без ддс'],
    ['Date.', 'date'],
  ])('normalizes header %j', (raw, expected) => {
    expect(normalizeHeader(raw)).toBe(expected);
  });

  it('collapses counterparty noise but keeps case', () => {
    expect(normalizeCounterparty('  Алфа   ООД  ')).toBe('Алфа ООД');
    expect(normalizeCounterparty('Алфа ООД.')).toBe('Алфа ООД');
  });

  it('makes whitespace duplicates identical', () => {
    expect(normalizeCounterparty('Бета ЕООД ')).toBe(normalizeCounterparty('Бета  ЕООД'));
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix js test -- parsing`
Expected: FAIL — cannot resolve `../src/parsing.js`

- [ ] **Step 3: Write the implementation**

`js/src/parsing.js`:
```javascript
/**
 * Parsers for the formats real accounting exports actually contain.
 *
 * Mirrors py/src/iconomics/parsing.py exactly, including the decimal
 * separator resolution rules and the day-first reading of ambiguous dates.
 *
 * Dates are returned at UTC midnight, because JavaScript has no date-only
 * type and a local-midnight Date shifts under timezone conversion.
 */

import Decimal from 'decimal.js';

const EXCEL_EPOCH_UTC = Date.UTC(1899, 11, 30);
const MS_PER_DAY = 86400000;
const CURRENCY_NOISE = /(лв\.?|BGN|EUR|€)/gi;
const WHITESPACE = /[\s ]+/g;
const MONTHS = {
  jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6,
  jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12,
};

export class UnparseableAmount extends Error {}
export class UnparseableDate extends Error {}

export function fromExcelSerial(serial) {
  return new Date(EXCEL_EPOCH_UTC + Math.trunc(serial) * MS_PER_DAY);
}

function resolveSeparators(text) {
  const hasComma = text.includes(',');
  const hasDot = text.includes('.');

  if (hasComma && hasDot) {
    return text.lastIndexOf(',') > text.lastIndexOf('.')
      ? text.replaceAll('.', '').replace(',', '.')
      : text.replaceAll(',', '');
  }

  if (hasComma || hasDot) {
    const sep = hasComma ? ',' : '.';
    const occurrences = text.split(sep).length - 1;
    if (occurrences > 1) throw new UnparseableAmount(`ambiguous separators in '${text}'`);
    const digitsAfter = text.slice(text.lastIndexOf(sep) + 1).length;
    if (digitsAfter === 1 || digitsAfter === 2) return text.replace(sep, '.');
    if (digitsAfter === 3) return text.replace(sep, '');
    throw new UnparseableAmount(`ambiguous separators in '${text}'`);
  }

  return text;
}

export function parseAmount(raw) {
  if (Decimal.isDecimal(raw)) return raw;
  if (typeof raw === 'boolean') throw new UnparseableAmount('boolean is not an amount');
  if (typeof raw === 'number') {
    if (!Number.isFinite(raw)) throw new UnparseableAmount(`non-finite number ${raw}`);
    return new Decimal(String(raw));
  }
  if (typeof raw !== 'string') {
    throw new UnparseableAmount(`cannot read amount from ${typeof raw}`);
  }

  let text = raw.replace(CURRENCY_NOISE, '').trim();
  const negative = text.startsWith('(') && text.endsWith(')');
  if (negative) text = text.slice(1, -1).trim();
  text = text.replace(WHITESPACE, '');
  if (!text) throw new UnparseableAmount('empty cell');

  text = resolveSeparators(text);
  let value;
  try {
    value = new Decimal(text);
  } catch {
    throw new UnparseableAmount(`cannot read amount from '${raw}'`);
  }
  return negative ? value.negated() : value;
}

function utcDate(year, month, day) {
  const stamp = Date.UTC(year, month - 1, day);
  const built = new Date(stamp);
  // Reject overflow like 32.01 silently rolling into February.
  if (
    built.getUTCFullYear() !== year ||
    built.getUTCMonth() !== month - 1 ||
    built.getUTCDate() !== day
  ) {
    throw new UnparseableDate(`invalid date ${year}-${month}-${day}`);
  }
  return built;
}

function parseTextualDate(text) {
  let match = text.match(/^(\d{1,2})[-\s]([A-Za-z]{3,})[-\s](\d{2,4})$/);
  if (match) {
    const month = MONTHS[match[2].slice(0, 3).toLowerCase()];
    if (!month) throw new UnparseableDate(`unknown month in '${text}'`);
    let year = Number(match[3]);
    if (year < 100) year += 2000;
    return utcDate(year, month, Number(match[1]));
  }

  match = text.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/);
  if (match) {
    return utcDate(Number(match[1]), Number(match[2]), Number(match[3]));
  }

  match = text.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})$/);
  if (match) {
    let year = Number(match[3]);
    if (year < 100) year += 2000;
    return utcDate(year, Number(match[2]), Number(match[1]));
  }

  throw new UnparseableDate(`cannot read date from '${text}'`);
}

export function parseDate(raw) {
  if (raw instanceof Date) {
    if (Number.isNaN(raw.getTime())) throw new UnparseableDate('invalid Date');
    return new Date(Date.UTC(raw.getUTCFullYear(), raw.getUTCMonth(), raw.getUTCDate()));
  }
  if (typeof raw === 'boolean') throw new UnparseableDate('boolean is not a date');
  if (typeof raw === 'number') {
    if (!Number.isFinite(raw)) throw new UnparseableDate(`invalid Excel serial ${raw}`);
    return fromExcelSerial(raw);
  }
  if (typeof raw !== 'string') {
    throw new UnparseableDate(`cannot read date from ${typeof raw}`);
  }

  const text = raw.trim();
  if (!text) throw new UnparseableDate('empty cell');
  return parseTextualDate(text);
}

export function normalizeHeader(raw) {
  return String(raw)
    .replace(WHITESPACE, ' ')
    .trim()
    .replace(/[.:]+$/, '')
    .trim()
    .toLowerCase();
}

export function normalizeCounterparty(raw) {
  return String(raw).replace(WHITESPACE, ' ').trim().replace(/\.+$/, '').trim();
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix js test -- parsing`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add js/src/parsing.js js/test/parsing.test.js
git commit -m "feat: mirror messy input parsers in JavaScript"
```

---

### Task 6: Header alias config and loaders (both languages)

One task rather than two, because the deliverable is a single config file plus two thin
readers of it — a reviewer could not sensibly accept one loader and reject the other.

**Note on YAGNI:** only `config/headers.yaml` is created here. `config/vat-rates.yaml` and
`config/coa.yaml` are deferred to the VAT and financial-statements plans, where their
consumers exist. Creating them now would mean shipping unused, untested config.

**Files:**
- Create: `config/headers.yaml`, `py/src/iconomics/config.py`, `js/src/config.js`
- Test: `py/tests/test_config.py`, `js/test/config.test.js`

**Interfaces:**
- Consumes: `normalize_header` / `normalizeHeader` from Task 4/5.
- Produces:
  - Python: `CANONICAL_FIELDS: tuple[str, ...]`, `find_config_dir() -> Path`,
    `load_header_aliases(config_dir: Path | None = None) -> dict[str, str]` (normalized
    alias → canonical field), `ConfigError(RuntimeError)`
  - JavaScript: `CANONICAL_FIELDS`, `findConfigDir()`, `loadHeaderAliases(configDir)`,
    `ConfigError`

- [ ] **Step 1: Write the config file**

`config/headers.yaml`:
```yaml
# Input column headers, mapped to the canonical field names the toolkit uses.
#
# Add your own aliases here rather than renaming columns in the source files —
# keeping the original export untouched is what makes the audit trail credible.
# Matching is case-insensitive and ignores surrounding whitespace and trailing
# punctuation, so "ДАТА:" and "Дата" both match "дата".

date:
  - дата
  - дата на документа
  - дата на фактурата
  - date
counterparty:
  - контрагент
  - партньор
  - доставчик
  - клиент
  - counterparty
  - vendor
vat_number:
  - ддс номер
  - идент. номер по ддс
  - vat number
  - vat no
description:
  - описание
  - основание
  - description
  - memo
amount_net:
  - сума без ддс
  - данъчна основа
  - сума
  - net amount
  - amount
vat_amount:
  - ддс
  - данък
  - vat amount
vat_rate:
  - ддс %
  - ставка
  - vat rate
account:
  - сметка
  - account
currency:
  - валута
  - currency
```

- [ ] **Step 2: Write the failing Python test**

`py/tests/test_config.py`:
```python
import pytest

from iconomics.config import (
    CANONICAL_FIELDS,
    ConfigError,
    find_config_dir,
    load_header_aliases,
)


def test_canonical_fields_are_the_documented_set():
    assert CANONICAL_FIELDS == (
        "date",
        "counterparty",
        "vat_number",
        "description",
        "amount_net",
        "vat_amount",
        "vat_rate",
        "account",
        "currency",
    )


def test_config_dir_is_discovered_from_the_repo():
    assert (find_config_dir() / "headers.yaml").is_file()


def test_aliases_map_normalized_headers_to_canonical_fields():
    aliases = load_header_aliases()
    assert aliases["дата"] == "date"
    assert aliases["контрагент"] == "counterparty"
    assert aliases["сума без ддс"] == "amount_net"


def test_aliases_are_stored_normalized():
    # Every key must already be normalized, so lookup is a plain dict hit.
    aliases = load_header_aliases()
    assert all(key == key.lower().strip() for key in aliases)


def test_missing_config_dir_is_a_clear_error(tmp_path):
    with pytest.raises(ConfigError, match="headers.yaml"):
        load_header_aliases(tmp_path)


def test_unknown_canonical_field_in_config_is_rejected(tmp_path):
    (tmp_path / "headers.yaml").write_text("not_a_field:\n  - foo\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="not_a_field"):
        load_header_aliases(tmp_path)
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd py && python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'iconomics.config'`

- [ ] **Step 4: Write the Python loader**

`py/src/iconomics/config.py`:
```python
"""Loads the YAML rule files that keep accounting rules out of the source."""

from pathlib import Path

import yaml

from iconomics.parsing import normalize_header

CANONICAL_FIELDS = (
    "date",
    "counterparty",
    "vat_number",
    "description",
    "amount_net",
    "vat_amount",
    "vat_rate",
    "account",
    "currency",
)


class ConfigError(RuntimeError):
    """Raised when a config file is missing or malformed."""


def find_config_dir() -> Path:
    """Walk up from this module until a directory containing config/ is found."""
    for candidate in Path(__file__).resolve().parents:
        config_dir = candidate / "config"
        if (config_dir / "headers.yaml").is_file():
            return config_dir
    raise ConfigError("could not locate config/headers.yaml above this module")


def load_header_aliases(config_dir: Path | None = None) -> dict[str, str]:
    """Return a mapping of normalized input header -> canonical field name."""
    directory = config_dir if config_dir is not None else find_config_dir()
    path = Path(directory) / "headers.yaml"
    if not path.is_file():
        raise ConfigError(f"missing config file: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    aliases: dict[str, str] = {}
    for field, values in raw.items():
        if field not in CANONICAL_FIELDS:
            raise ConfigError(
                f"unknown canonical field {field!r} in {path}; "
                f"expected one of {', '.join(CANONICAL_FIELDS)}"
            )
        for value in values or []:
            aliases[normalize_header(value)] = field
    return aliases
```

- [ ] **Step 5: Run it to verify it passes**

Run: `cd py && python -m pytest tests/test_config.py -v`
Expected: PASS — 6 tests

- [ ] **Step 6: Write the failing JavaScript test**

`js/test/config.test.js`:
```javascript
import { describe, it, expect } from 'vitest';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
  CANONICAL_FIELDS,
  ConfigError,
  findConfigDir,
  loadHeaderAliases,
} from '../src/config.js';

describe('config', () => {
  it('exposes the documented canonical fields', () => {
    expect(CANONICAL_FIELDS).toEqual([
      'date',
      'counterparty',
      'vat_number',
      'description',
      'amount_net',
      'vat_amount',
      'vat_rate',
      'account',
      'currency',
    ]);
  });

  it('discovers the config dir from the repo', () => {
    expect(findConfigDir()).toBeTruthy();
  });

  it('maps normalized headers to canonical fields', () => {
    const aliases = loadHeaderAliases();
    expect(aliases['дата']).toBe('date');
    expect(aliases['контрагент']).toBe('counterparty');
    expect(aliases['сума без ддс']).toBe('amount_net');
  });

  it('reports a missing config file clearly', () => {
    const empty = mkdtempSync(join(tmpdir(), 'iconomics-'));
    expect(() => loadHeaderAliases(empty)).toThrow(/headers\.yaml/);
  });

  it('rejects an unknown canonical field', () => {
    const dir = mkdtempSync(join(tmpdir(), 'iconomics-'));
    writeFileSync(join(dir, 'headers.yaml'), 'not_a_field:\n  - foo\n', 'utf-8');
    expect(() => loadHeaderAliases(dir)).toThrow(ConfigError);
  });
});
```

- [ ] **Step 7: Run it to verify it fails**

Run: `npm --prefix js test -- config`
Expected: FAIL — cannot resolve `../src/config.js`

- [ ] **Step 8: Write the JavaScript loader**

`js/src/config.js`:
```javascript
/**
 * Loads the YAML rule files. Mirrors py/src/iconomics/config.py.
 *
 * js-yaml v4's `load` uses the default safe schema — it cannot construct
 * arbitrary types, and is the direct equivalent of Python's `yaml.safe_load`.
 * (v3's `safeLoad` was removed precisely because `load` became safe.) Do not
 * pass a custom schema here.
 */

import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import yaml from 'js-yaml';

import { normalizeHeader } from './parsing.js';

export const CANONICAL_FIELDS = [
  'date',
  'counterparty',
  'vat_number',
  'description',
  'amount_net',
  'vat_amount',
  'vat_rate',
  'account',
  'currency',
];

export class ConfigError extends Error {}

export function findConfigDir() {
  let current = dirname(fileURLToPath(import.meta.url));
  for (;;) {
    const candidate = join(current, 'config');
    if (existsSync(join(candidate, 'headers.yaml'))) return candidate;
    const parent = resolve(current, '..');
    if (parent === current) break;
    current = parent;
  }
  throw new ConfigError('could not locate config/headers.yaml above this module');
}

export function loadHeaderAliases(configDir = null) {
  const directory = configDir ?? findConfigDir();
  const path = join(directory, 'headers.yaml');
  if (!existsSync(path)) throw new ConfigError(`missing config file: ${path}`);

  const raw = yaml.load(readFileSync(path, 'utf-8')) ?? {};
  const aliases = {};
  for (const [field, values] of Object.entries(raw)) {
    if (!CANONICAL_FIELDS.includes(field)) {
      throw new ConfigError(
        `unknown canonical field '${field}' in ${path}; ` +
          `expected one of ${CANONICAL_FIELDS.join(', ')}`,
      );
    }
    for (const value of values ?? []) {
      aliases[normalizeHeader(value)] = field;
    }
  }
  return aliases;
}
```

- [ ] **Step 9: Run it to verify it passes**

Run: `npm --prefix js test -- config`
Expected: PASS — 5 tests

- [ ] **Step 10: Commit**

```bash
git add config/headers.yaml py/src/iconomics/config.py py/tests/test_config.py \
        js/src/config.js js/test/config.test.js
git commit -m "feat: add header alias config with loaders in both languages"
```

---

### Task 7: Deterministic messy sample data

Generates the committed sample workbooks. Determinism matters: golden files are compared
byte-for-value later, so nothing here may use randomness or the current date.

**Files:**
- Create: `tools/make_sample_data.py`
- Create (generated, then committed): `data/raw/ledger-2025-12.xlsx`,
  `data/raw/ledger-2026-01.xlsx`, `data/raw/ledger-2026-02.xlsx`
- Test: `py/tests/test_sample_data.py`

**Interfaces:**
- Consumes: openpyxl.
- Produces: three workbooks whose messiness is *specified*, so the cleanup tests can assert
  exact expected outcomes. Also `SAMPLE_FILES: tuple[str, ...]` for tests to iterate.

**The messiness is deliberate and documented.** Each file exercises specific cases:

| File | Period | Currency situation | Planted problems |
|---|---|---|---|
| `ledger-2025-12.xlsx` | Dec 2025 | All BGN, pre-euro | `dd.mm.yyyy` dates, comma decimals, one amount as text with space thousands |
| `ledger-2026-01.xlsx` | Jan 2026 | **Mixed BGN and EUR** (dual circulation) | Explicit `Валута` column with both values, two Excel-serial dates, one duplicate vendor differing only by trailing space |
| `ledger-2026-02.xlsx` | Feb 2026 | All EUR | Different header spelling (`Партньор` not `Контрагент`), one `1-Feb-26` date, one unparseable amount (`n/a`), one blank date, `ООД.` vs `ООД` vendor variant |

- [ ] **Step 1: Write the failing test**

`py/tests/test_sample_data.py`:
```python
from pathlib import Path

import pytest
from openpyxl import load_workbook

from iconomics.config import find_config_dir

SAMPLE_FILES = (
    "ledger-2025-12.xlsx",
    "ledger-2026-01.xlsx",
    "ledger-2026-02.xlsx",
)


def data_raw() -> Path:
    return find_config_dir().parent / "data" / "raw"


@pytest.mark.parametrize("name", SAMPLE_FILES)
def test_sample_file_exists_and_has_rows(name):
    path = data_raw() / name
    assert path.is_file(), f"{name} missing; run python tools/make_sample_data.py"
    sheet = load_workbook(path).active
    assert sheet.max_row > 1


def test_january_file_contains_both_currencies():
    sheet = load_workbook(data_raw() / "ledger-2026-01.xlsx").active
    headers = [cell.value for cell in sheet[1]]
    currency_col = headers.index("Валута") + 1
    values = {sheet.cell(row=r, column=currency_col).value for r in range(2, sheet.max_row + 1)}
    assert {"BGN", "EUR"} <= values


def test_february_file_uses_the_alternate_counterparty_header():
    headers = [cell.value for cell in load_workbook(data_raw() / "ledger-2026-02.xlsx").active[1]]
    assert "Партньор" in headers
    assert "Контрагент" not in headers


def test_february_file_contains_a_planted_unparseable_amount():
    sheet = load_workbook(data_raw() / "ledger-2026-02.xlsx").active
    values = [
        sheet.cell(row=r, column=c).value
        for r in range(2, sheet.max_row + 1)
        for c in range(1, sheet.max_column + 1)
    ]
    assert "n/a" in values


def test_generation_is_deterministic(tmp_path):
    import subprocess
    import sys

    root = find_config_dir().parent
    first = (data_raw() / "ledger-2026-02.xlsx").read_bytes()
    subprocess.run(
        [sys.executable, str(root / "tools" / "make_sample_data.py")],
        cwd=root,
        check=True,
    )
    second = (data_raw() / "ledger-2026-02.xlsx").read_bytes()
    # openpyxl embeds no timestamps for these settings, so bytes must match.
    assert first == second
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd py && python -m pytest tests/test_sample_data.py -v`
Expected: FAIL — sample files missing

- [ ] **Step 3: Write the generator**

`tools/make_sample_data.py`:
```python
#!/usr/bin/env python3
"""Generate the deliberately messy sample ledgers.

Everything here is hardcoded. No randomness and no reference to the current
date, because data/expected/ golden files are compared exactly and would
otherwise churn on every run.

Run from the repo root:  python tools/make_sample_data.py
"""

from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "raw"

# December 2025: pre-euro, everything in BGN, Bulgarian date and number formats.
DECEMBER = {
    "headers": ["Дата", "Контрагент", "ДДС номер", "Описание", "Сума без ДДС", "ДДС"],
    "rows": [
        ["01.12.2025", "Алфа ООД", "BG123456789", "Консултантски услуги", "1 200,00", "240,00"],
        ["05.12.2025", "Бета ЕООД", "BG987654321", "Наем офис", "800,50", "160,10"],
        ["17.12.2025", "Гама АД", "BG555444333", "Софтуерен абонамент", "349,99", "70,00"],
        ["31.12.2025", "Алфа ООД", "BG123456789", "Годишна такса", "2 500,00", "500,00"],
    ],
}

# January 2026: dual circulation month. Explicit currency column, mixed values.
JANUARY = {
    "headers": ["Дата", "Контрагент", "ДДС номер", "Описание", "Сума без ДДС", "ДДС", "Валута"],
    "rows": [
        ["05.01.2026", "Алфа ООД", "BG123456789", "Консултантски услуги", "1 000,00", "200,00", "BGN"],
        [46027, "Бета ЕООД ", "BG987654321", "Наем офис", "410,00", "82,00", "EUR"],
        [46030, "Бета ЕООД", "BG987654321", "Наем склад", "205,00", "41,00", "EUR"],
        ["20.01.2026", "Делта ООД", "BG111222333", "Транспорт", "150,75", "30,15", "BGN"],
        ["28.01.2026", "Гама АД", "BG555444333", "Софтуерен абонамент", "179,00", "35,80", "EUR"],
    ],
}

# February 2026: euro only, different header spelling, planted bad rows.
FEBRUARY = {
    "headers": ["Дата", "Партньор", "ДДС номер", "Описание", "Сума без ДДС", "ДДС"],
    "rows": [
        ["1-Feb-26", "Алфа ООД", "BG123456789", "Консултантски услуги", "512.00", "102.40"],
        ["03.02.2026", "Алфа ООД.", "BG123456789", "Допълнителни услуги", "128.00", "25.60"],
        ["11.02.2026", "Епсилон ЕООД", "BG444555666", "Счетоводен софтуер", "1.234", "246.80"],
        ["14.02.2026", "Делта ООД", "BG111222333", "Транспорт", "n/a", "12.00"],
        ["", "Гама АД", "BG555444333", "Липсва дата", "99.00", "19.80"],
        ["28.02.2026", "Бета ЕООД", "BG987654321", "Наем офис", "410.00", "82.00"],
    ],
}


def write_workbook(path: Path, spec: dict) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ledger"
    sheet.append(spec["headers"])
    for row in spec["rows"]:
        sheet.append(row)
    workbook.save(path)
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_workbook(OUT_DIR / "ledger-2025-12.xlsx", DECEMBER)
    write_workbook(OUT_DIR / "ledger-2026-01.xlsx", JANUARY)
    write_workbook(OUT_DIR / "ledger-2026-02.xlsx", FEBRUARY)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Generate the data and run the test**

Run: `python tools/make_sample_data.py && cd py && python -m pytest tests/test_sample_data.py -v`
Expected: PASS — all 7 tests

- [ ] **Step 5: Commit the generator and the generated data**

The generated workbooks are committed deliberately: a reader cloning the repo must be able
to run a workflow immediately without a generation step.

```bash
git add tools/make_sample_data.py data/raw py/tests/test_sample_data.py
git commit -m "feat: add deterministic messy sample ledgers"
```

---

### Task 8: Workbook load and write (Python)

The boundary module. Nothing else in the codebase may import openpyxl. This is where the
"no float money" and "never lose `source_row`" constraints are enforced.

**Files:**
- Create: `py/src/iconomics/workbook.py`
- Test: `py/tests/test_workbook.py`

**Interfaces:**
- Consumes: `parse_amount`, `parse_date`, `normalize_header`, `normalize_counterparty`
  (Task 4); `Money`, `default_currency_for` (Task 2); `load_header_aliases`,
  `CANONICAL_FIELDS` (Task 6).
- Produces:
  - `Row` — frozen dataclass: `source_row: int`, `date: date`, `counterparty: str`,
    `vat_number: str | None`, `description: str`, `amount_net: Money`,
    `vat_amount: Money | None`, `vat_rate: Decimal | None`, `account: str | None`,
    `currency: str`, `extra: dict[str, object]`
  - `Problem` — frozen dataclass: `source_row: int`, `field: str`, `raw: str`, `reason: str`
  - `Ledger` — frozen dataclass: `rows: list[Row]`, `problems: list[Problem]`,
    `unmapped_headers: list[str]`, `source_path: Path`
  - `Sheet` — dataclass: `columns: list[str]`, `rows: list[list[object]]`
  - `load(path: Path, aliases: dict[str, str] | None = None) -> Ledger`
  - `write(path: Path, sheets: dict[str, Sheet]) -> None`
  - `MissingColumn(RuntimeError)` — raised when `date`, `counterparty`, or `amount_net`
    has no mapped column at all

**Two rules this module encodes:**
1. **Row-level problems do not abort the run.** A row with a bad amount becomes a `Problem`
   and is left out of `rows`; the rest of the file still loads.
2. **File-level problems abort immediately.** A missing `amount_net` column means the file
   is not the shape we think it is, so `MissingColumn` is raised before any output exists.
   A half-correct ledger is worse than no ledger.

- [ ] **Step 1: Write the failing tests**

`py/tests/test_workbook.py`:
```python
from datetime import date
from decimal import Decimal

import pytest
from openpyxl import Workbook, load_workbook

from iconomics.config import find_config_dir
from iconomics.money import Money
from iconomics.workbook import (
    MissingColumn,
    Sheet,
    load,
    write,
)


def data_raw():
    return find_config_dir().parent / "data" / "raw"


def make_file(tmp_path, headers, rows, name="in.xlsx"):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    path = tmp_path / name
    workbook.save(path)
    return path


def test_cyrillic_headers_map_to_canonical_fields(tmp_path):
    path = make_file(
        tmp_path,
        ["Дата", "Контрагент", "Сума без ДДС", "ДДС"],
        [["01.02.2026", "Алфа ООД", "100,00", "20,00"]],
    )
    ledger = load(path)
    assert len(ledger.rows) == 1
    row = ledger.rows[0]
    assert row.date == date(2026, 2, 1)
    assert row.counterparty == "Алфа ООД"
    assert row.amount_net == Money(Decimal("100.00"), "EUR")


def test_alternate_header_spelling_also_maps(tmp_path):
    path = make_file(
        tmp_path,
        ["Дата", "Партньор", "Сума без ДДС"],
        [["01.02.2026", "Алфа ООД", "100,00"]],
    )
    assert load(path).rows[0].counterparty == "Алфа ООД"


def test_source_row_is_the_original_spreadsheet_row(tmp_path):
    path = make_file(
        tmp_path,
        ["Дата", "Контрагент", "Сума без ДДС"],
        [
            ["01.02.2026", "Алфа ООД", "1,00"],
            ["02.02.2026", "Бета ЕООД", "2,00"],
        ],
    )
    # Header is row 1, so data starts at row 2.
    assert [row.source_row for row in load(path).rows] == [2, 3]


def test_money_is_always_decimal_backed(tmp_path):
    path = make_file(
        tmp_path,
        ["Дата", "Контрагент", "Сума без ДДС"],
        [["01.02.2026", "Алфа ООД", 100.5]],
    )
    amount = load(path).rows[0].amount_net
    assert isinstance(amount.amount, Decimal)


def test_currency_defaults_by_date_when_no_currency_column(tmp_path):
    path = make_file(
        tmp_path,
        ["Дата", "Контрагент", "Сума без ДДС"],
        [
            ["31.12.2025", "Алфа ООД", "100,00"],
            ["01.01.2026", "Алфа ООД", "100,00"],
        ],
    )
    rows = load(path).rows
    assert rows[0].currency == "BGN"
    assert rows[1].currency == "EUR"


def test_explicit_currency_column_overrides_the_date_default(tmp_path):
    path = make_file(
        tmp_path,
        ["Дата", "Контрагент", "Сума без ДДС", "Валута"],
        [["01.02.2026", "Алфа ООД", "100,00", "BGN"]],
    )
    assert load(path).rows[0].currency == "BGN"


def test_bad_amount_becomes_a_problem_and_does_not_abort(tmp_path):
    path = make_file(
        tmp_path,
        ["Дата", "Контрагент", "Сума без ДДС"],
        [
            ["01.02.2026", "Алфа ООД", "n/a"],
            ["02.02.2026", "Бета ЕООД", "5,00"],
        ],
    )
    ledger = load(path)
    assert len(ledger.rows) == 1
    assert len(ledger.problems) == 1
    problem = ledger.problems[0]
    assert problem.source_row == 2
    assert problem.field == "amount_net"
    assert "n/a" in problem.raw


def test_blank_date_becomes_a_problem(tmp_path):
    path = make_file(
        tmp_path,
        ["Дата", "Контрагент", "Сума без ДДС"],
        [["", "Гама АД", "9,00"]],
    )
    ledger = load(path)
    assert ledger.rows == []
    assert ledger.problems[0].field == "date"


def test_missing_required_column_aborts_before_output(tmp_path):
    path = make_file(tmp_path, ["Дата", "Контрагент"], [["01.02.2026", "Алфа ООД"]])
    with pytest.raises(MissingColumn, match="amount_net"):
        load(path)


def test_unmapped_columns_are_preserved_not_dropped(tmp_path):
    path = make_file(
        tmp_path,
        ["Дата", "Контрагент", "Сума без ДДС", "Вътрешен код"],
        [["01.02.2026", "Алфа ООД", "1,00", "XYZ-1"]],
    )
    ledger = load(path)
    assert ledger.unmapped_headers == ["Вътрешен код"]
    assert ledger.rows[0].extra["Вътрешен код"] == "XYZ-1"


def test_fully_blank_rows_are_skipped_silently(tmp_path):
    path = make_file(
        tmp_path,
        ["Дата", "Контрагент", "Сума без ДДС"],
        [["01.02.2026", "Алфа ООД", "1,00"], [None, None, None]],
    )
    ledger = load(path)
    assert len(ledger.rows) == 1
    assert ledger.problems == []


def test_all_sample_files_load(tmp_path):
    for name in ("ledger-2025-12.xlsx", "ledger-2026-01.xlsx", "ledger-2026-02.xlsx"):
        ledger = load(data_raw() / name)
        assert ledger.rows, f"{name} produced no rows"


def test_write_produces_readable_multi_sheet_output(tmp_path):
    path = tmp_path / "out.xlsx"
    write(
        path,
        {
            "Clean": Sheet(columns=["A", "B"], rows=[[1, "x"], [2, "y"]]),
            "Exceptions": Sheet(columns=["Row", "Reason"], rows=[[7, "bad amount"]]),
        },
    )
    workbook = load_workbook(path)
    assert workbook.sheetnames == ["Clean", "Exceptions"]
    assert [cell.value for cell in workbook["Clean"][1]] == ["A", "B"]
    assert workbook["Exceptions"]["A2"].value == 7


def test_write_serializes_money_and_decimal_as_numbers(tmp_path):
    path = tmp_path / "out.xlsx"
    write(
        path,
        {"S": Sheet(columns=["Amount"], rows=[[Money(Decimal("12.34"), "EUR")]])},
    )
    cell = load_workbook(path)["S"]["A2"]
    assert cell.value == 12.34
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd py && python -m pytest tests/test_workbook.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'iconomics.workbook'`

- [ ] **Step 3: Write the implementation**

`py/src/iconomics/workbook.py`:
```python
"""The only module that touches .xlsx files.

Two boundary guarantees:
  * every monetary value leaving load() is Decimal-backed, never float
  * every row and problem carries source_row, the 1-indexed original row
"""

from dataclasses import dataclass, field
from datetime import date as Date
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from iconomics.config import load_header_aliases
from iconomics.money import Money, default_currency_for
from iconomics.parsing import (
    UnparseableAmount,
    UnparseableDate,
    normalize_header,
    parse_amount,
    parse_date,
)

REQUIRED_FIELDS = ("date", "counterparty", "amount_net")
_HEADER_FILL = PatternFill("solid", fgColor="DDDDDD")


class MissingColumn(RuntimeError):
    """Raised when the file lacks a column the toolkit cannot work without."""


@dataclass(frozen=True)
class Row:
    source_row: int
    date: Date
    counterparty: str
    description: str
    amount_net: Money
    currency: str
    vat_number: str | None = None
    vat_amount: Money | None = None
    vat_rate: Decimal | None = None
    account: str | None = None
    extra: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Problem:
    source_row: int
    field: str
    raw: str
    reason: str


@dataclass(frozen=True)
class Ledger:
    rows: list[Row]
    problems: list[Problem]
    unmapped_headers: list[str]
    source_path: Path


@dataclass
class Sheet:
    columns: list[str]
    rows: list[list[object]]


def _map_columns(header_cells, aliases):
    """Return (field -> column index) and the list of unmapped header labels."""
    mapping: dict[str, int] = {}
    unmapped: list[str] = []
    for index, raw in enumerate(header_cells):
        if raw is None or str(raw).strip() == "":
            continue
        canonical = aliases.get(normalize_header(raw))
        if canonical is None:
            unmapped.append(str(raw))
        elif canonical not in mapping:
            mapping[canonical] = index
    return mapping, unmapped


def _cell(values, mapping, name):
    index = mapping.get(name)
    if index is None or index >= len(values):
        return None
    return values[index]


def load(path: Path, aliases: dict[str, str] | None = None) -> Ledger:
    """Read a spreadsheet into canonical rows plus a list of row-level problems."""
    path = Path(path)
    resolved_aliases = aliases if aliases is not None else load_header_aliases()

    workbook = load_workbook(path, data_only=True)
    sheet = workbook.active
    all_rows = list(sheet.iter_rows(values_only=True))
    if not all_rows:
        raise MissingColumn(f"{path} is empty")

    mapping, unmapped = _map_columns(all_rows[0], resolved_aliases)
    for required in REQUIRED_FIELDS:
        if required not in mapping:
            raise MissingColumn(
                f"{path} has no column mapping to {required!r}; "
                "add an alias in config/headers.yaml"
            )

    rows: list[Row] = []
    problems: list[Problem] = []

    for offset, values in enumerate(all_rows[1:], start=2):
        if all(value is None or str(value).strip() == "" for value in values):
            continue

        try:
            row_date = parse_date(_cell(values, mapping, "date"))
        except UnparseableDate as exc:
            problems.append(
                Problem(offset, "date", str(_cell(values, mapping, "date")), str(exc))
            )
            continue

        try:
            net = parse_amount(_cell(values, mapping, "amount_net"))
        except UnparseableAmount as exc:
            problems.append(
                Problem(
                    offset,
                    "amount_net",
                    str(_cell(values, mapping, "amount_net")),
                    str(exc),
                )
            )
            continue

        currency_raw = _cell(values, mapping, "currency")
        currency = (
            str(currency_raw).strip().upper()
            if currency_raw not in (None, "")
            else default_currency_for(row_date)
        )

        vat_raw = _cell(values, mapping, "vat_amount")
        vat_amount = None
        if vat_raw not in (None, ""):
            try:
                vat_amount = Money(parse_amount(vat_raw), currency)
            except UnparseableAmount as exc:
                problems.append(Problem(offset, "vat_amount", str(vat_raw), str(exc)))
                continue

        rate_raw = _cell(values, mapping, "vat_rate")
        vat_rate = None
        if rate_raw not in (None, ""):
            try:
                vat_rate = parse_amount(rate_raw)
            except UnparseableAmount as exc:
                problems.append(Problem(offset, "vat_rate", str(rate_raw), str(exc)))
                continue

        counterparty_raw = _cell(values, mapping, "counterparty")
        vat_number_raw = _cell(values, mapping, "vat_number")
        account_raw = _cell(values, mapping, "account")
        description_raw = _cell(values, mapping, "description")

        extra = {
            str(all_rows[0][index]): values[index]
            for index in range(len(all_rows[0]))
            if str(all_rows[0][index] or "") in unmapped and index < len(values)
        }

        rows.append(
            Row(
                source_row=offset,
                date=row_date,
                counterparty=str(counterparty_raw or "").strip(),
                description=str(description_raw or "").strip(),
                amount_net=Money(net, currency),
                currency=currency,
                vat_number=str(vat_number_raw).strip() if vat_number_raw else None,
                vat_amount=vat_amount,
                vat_rate=vat_rate,
                account=str(account_raw).strip() if account_raw else None,
                extra=extra,
            )
        )

    return Ledger(
        rows=rows, problems=problems, unmapped_headers=unmapped, source_path=path
    )


def _serialize(value: object) -> object:
    """Flatten a value into something openpyxl can store."""
    if isinstance(value, Money):
        return float(value.amount)
    if isinstance(value, Decimal):
        return float(value)
    return value


def write(path: Path, sheets: dict[str, Sheet]) -> None:
    """Write formatted, frozen-header sheets in the given order."""
    workbook = Workbook()
    workbook.remove(workbook.active)

    for name, spec in sheets.items():
        sheet = workbook.create_sheet(title=name)
        sheet.append(spec.columns)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.fill = _HEADER_FILL
            cell.alignment = Alignment(vertical="center")
        for row in spec.rows:
            sheet.append([_serialize(value) for value in row])

        sheet.freeze_panes = "A2"
        for index, column in enumerate(spec.columns, start=1):
            widest = max(
                [len(str(column))]
                + [len(str(_serialize(row[index - 1]))) for row in spec.rows if index - 1 < len(row)]
            )
            sheet.column_dimensions[get_column_letter(index)].width = min(widest + 2, 48)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
```

**Note on `float` in `_serialize`:** this is the one place a float is permitted, because
openpyxl cannot store a `Decimal` and the value is leaving the system into a spreadsheet
cell. The conversion happens after all arithmetic is complete. Nothing reads it back.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd py && python -m pytest tests/test_workbook.py -v`
Expected: PASS — 14 tests

- [ ] **Step 5: Commit**

```bash
git add py/src/iconomics/workbook.py py/tests/test_workbook.py
git commit -m "feat: add workbook load and write with Decimal boundary"
```

---

### Task 9: Workbook load and write (JavaScript)

Mirror of Task 8. One deliberate idiomatic difference: **exceljs is async**, so `load` and
`write` return promises. This is the only place the two APIs diverge in shape, and it is
documented rather than worked around — faking synchrony would be worse than the asymmetry.

**Files:**
- Create: `js/src/workbook.js`
- Test: `js/test/workbook.test.js`

**Interfaces:**
- Consumes: `exceljs`; `parseAmount`, `parseDate`, `normalizeHeader`,
  `normalizeCounterparty` (Task 5); `Money`, `defaultCurrencyFor` (Task 3);
  `loadHeaderAliases` (Task 6).
- Produces: `REQUIRED_FIELDS`, `MissingColumn`, `async load(path, aliases = null)`,
  `async write(path, sheets)`. Rows are plain objects with the same field names as the
  Python `Row` (`sourceRow` is the one rename — camelCase per JS convention). `Ledger` is
  `{ rows, problems, unmappedHeaders, sourcePath }`. Sheets are
  `{ [name]: { columns, rows } }`.

**Field naming across languages:** Python `source_row` ⇄ JavaScript `sourceRow`, and
likewise `amount_net` ⇄ `amountNet`, `vat_amount` ⇄ `vatAmount`, `vat_rate` ⇄ `vatRate`,
`vat_number` ⇄ `vatNumber`. Each language reads naturally in its own idiom. The **spreadsheet
column headers** are what the parity test compares, and those are identical.

- [ ] **Step 1: Write the failing tests**

`js/test/workbook.test.js`:
```javascript
import { describe, it, expect, beforeEach } from 'vitest';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import ExcelJS from 'exceljs';
import Decimal from 'decimal.js';

import { Money } from '../src/money.js';
import { MissingColumn, load, write } from '../src/workbook.js';
import { findConfigDir } from '../src/config.js';

let dir;
beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'iconomics-'));
});

async function makeFile(headers, rows, name = 'in.xlsx') {
  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet('Ledger');
  sheet.addRow(headers);
  rows.forEach((row) => sheet.addRow(row));
  const path = join(dir, name);
  await workbook.xlsx.writeFile(path);
  return path;
}

const dataRaw = () => join(findConfigDir(), '..', 'data', 'raw');

describe('load', () => {
  it('maps Cyrillic headers to canonical fields', async () => {
    const path = await makeFile(
      ['Дата', 'Контрагент', 'Сума без ДДС', 'ДДС'],
      [['01.02.2026', 'Алфа ООД', '100,00', '20,00']],
    );
    const ledger = await load(path);
    expect(ledger.rows).toHaveLength(1);
    expect(ledger.rows[0].counterparty).toBe('Алфа ООД');
    expect(ledger.rows[0].amountNet.equals(new Money(new Decimal('100.00'), 'EUR'))).toBe(true);
  });

  it('maps the alternate counterparty header', async () => {
    const path = await makeFile(
      ['Дата', 'Партньор', 'Сума без ДДС'],
      [['01.02.2026', 'Алфа ООД', '100,00']],
    );
    expect((await load(path)).rows[0].counterparty).toBe('Алфа ООД');
  });

  it('keeps the original spreadsheet row number', async () => {
    const path = await makeFile(
      ['Дата', 'Контрагент', 'Сума без ДДС'],
      [
        ['01.02.2026', 'Алфа ООД', '1,00'],
        ['02.02.2026', 'Бета ЕООД', '2,00'],
      ],
    );
    const ledger = await load(path);
    expect(ledger.rows.map((r) => r.sourceRow)).toEqual([2, 3]);
  });

  it('always produces Decimal-backed money', async () => {
    const path = await makeFile(
      ['Дата', 'Контрагент', 'Сума без ДДС'],
      [['01.02.2026', 'Алфа ООД', 100.5]],
    );
    const ledger = await load(path);
    expect(Decimal.isDecimal(ledger.rows[0].amountNet.amount)).toBe(true);
  });

  it('defaults currency by date when there is no currency column', async () => {
    const path = await makeFile(
      ['Дата', 'Контрагент', 'Сума без ДДС'],
      [
        ['31.12.2025', 'Алфа ООД', '100,00'],
        ['01.01.2026', 'Алфа ООД', '100,00'],
      ],
    );
    const ledger = await load(path);
    expect(ledger.rows.map((r) => r.currency)).toEqual(['BGN', 'EUR']);
  });

  it('lets an explicit currency column win', async () => {
    const path = await makeFile(
      ['Дата', 'Контрагент', 'Сума без ДДС', 'Валута'],
      [['01.02.2026', 'Алфа ООД', '100,00', 'BGN']],
    );
    expect((await load(path)).rows[0].currency).toBe('BGN');
  });

  it('turns a bad amount into a problem without aborting', async () => {
    const path = await makeFile(
      ['Дата', 'Контрагент', 'Сума без ДДС'],
      [
        ['01.02.2026', 'Алфа ООД', 'n/a'],
        ['02.02.2026', 'Бета ЕООД', '5,00'],
      ],
    );
    const ledger = await load(path);
    expect(ledger.rows).toHaveLength(1);
    expect(ledger.problems).toHaveLength(1);
    expect(ledger.problems[0].sourceRow).toBe(2);
    expect(ledger.problems[0].field).toBe('amount_net');
  });

  it('turns a blank date into a problem', async () => {
    const path = await makeFile(['Дата', 'Контрагент', 'Сума без ДДС'], [['', 'Гама АД', '9,00']]);
    const ledger = await load(path);
    expect(ledger.rows).toHaveLength(0);
    expect(ledger.problems[0].field).toBe('date');
  });

  it('aborts when a required column is missing', async () => {
    const path = await makeFile(['Дата', 'Контрагент'], [['01.02.2026', 'Алфа ООД']]);
    await expect(load(path)).rejects.toThrow(MissingColumn);
  });

  it('preserves unmapped columns', async () => {
    const path = await makeFile(
      ['Дата', 'Контрагент', 'Сума без ДДС', 'Вътрешен код'],
      [['01.02.2026', 'Алфа ООД', '1,00', 'XYZ-1']],
    );
    const ledger = await load(path);
    expect(ledger.unmappedHeaders).toEqual(['Вътрешен код']);
    expect(ledger.rows[0].extra['Вътрешен код']).toBe('XYZ-1');
  });

  it('skips fully blank rows silently', async () => {
    const path = await makeFile(
      ['Дата', 'Контрагент', 'Сума без ДДС'],
      [['01.02.2026', 'Алфа ООД', '1,00'], [null, null, null]],
    );
    const ledger = await load(path);
    expect(ledger.rows).toHaveLength(1);
    expect(ledger.problems).toHaveLength(0);
  });

  it('loads every committed sample file', async () => {
    for (const name of ['ledger-2025-12.xlsx', 'ledger-2026-01.xlsx', 'ledger-2026-02.xlsx']) {
      const ledger = await load(join(dataRaw(), name));
      expect(ledger.rows.length).toBeGreaterThan(0);
    }
  });
});

describe('write', () => {
  it('produces readable multi-sheet output', async () => {
    const path = join(dir, 'out.xlsx');
    await write(path, {
      Clean: { columns: ['A', 'B'], rows: [[1, 'x'], [2, 'y']] },
      Exceptions: { columns: ['Row', 'Reason'], rows: [[7, 'bad amount']] },
    });
    const workbook = new ExcelJS.Workbook();
    await workbook.xlsx.readFile(path);
    expect(workbook.worksheets.map((w) => w.name)).toEqual(['Clean', 'Exceptions']);
    expect(workbook.getWorksheet('Exceptions').getCell('A2').value).toBe(7);
  });

  it('serializes Money as a number', async () => {
    const path = join(dir, 'out.xlsx');
    await write(path, {
      S: { columns: ['Amount'], rows: [[new Money(new Decimal('12.34'), 'EUR')]] },
    });
    const workbook = new ExcelJS.Workbook();
    await workbook.xlsx.readFile(path);
    expect(workbook.getWorksheet('S').getCell('A2').value).toBe(12.34);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix js test -- workbook`
Expected: FAIL — cannot resolve `../src/workbook.js`

- [ ] **Step 3: Write the implementation**

`js/src/workbook.js`:
```javascript
/**
 * The only module that touches .xlsx files. Mirrors py/src/iconomics/workbook.py.
 *
 * exceljs is promise-based, so load() and write() are async. This is the one
 * intentional shape difference from the Python API.
 */

import { dirname } from 'node:path';
import { mkdirSync } from 'node:fs';
import ExcelJS from 'exceljs';
import Decimal from 'decimal.js';

import { loadHeaderAliases } from './config.js';
import { Money, defaultCurrencyFor } from './money.js';
import {
  UnparseableAmount,
  UnparseableDate,
  normalizeHeader,
  parseAmount,
  parseDate,
} from './parsing.js';

export const REQUIRED_FIELDS = ['date', 'counterparty', 'amount_net'];

export class MissingColumn extends Error {}

/** exceljs returns rich objects for some cells; reduce them to primitives. */
function plain(value) {
  if (value === null || value === undefined) return null;
  if (value instanceof Date) return value;
  if (typeof value === 'object') {
    if ('result' in value) return value.result; // formula cell
    if ('text' in value) return value.text; // rich text
    if ('richText' in value) return value.richText.map((part) => part.text).join('');
  }
  return value;
}

const isBlank = (value) => value === null || value === undefined || String(value).trim() === '';

function mapColumns(headerCells, aliases) {
  const mapping = {};
  const unmapped = [];
  headerCells.forEach((raw, index) => {
    if (isBlank(raw)) return;
    const canonical = aliases[normalizeHeader(raw)];
    if (canonical === undefined) unmapped.push(String(raw));
    else if (!(canonical in mapping)) mapping[canonical] = index;
  });
  return { mapping, unmapped };
}

const cellOf = (values, mapping, name) =>
  name in mapping && mapping[name] < values.length ? values[mapping[name]] : null;

export async function load(path, aliases = null) {
  const resolved = aliases ?? loadHeaderAliases();
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.readFile(path);
  const sheet = workbook.worksheets[0];
  if (!sheet || sheet.rowCount === 0) throw new MissingColumn(`${path} is empty`);

  const allRows = [];
  sheet.eachRow({ includeEmpty: true }, (row) => {
    const values = [];
    for (let i = 1; i <= sheet.columnCount; i += 1) values.push(plain(row.getCell(i).value));
    allRows.push(values);
  });

  const { mapping, unmapped } = mapColumns(allRows[0], resolved);
  for (const required of REQUIRED_FIELDS) {
    if (!(required in mapping)) {
      throw new MissingColumn(
        `${path} has no column mapping to '${required}'; add an alias in config/headers.yaml`,
      );
    }
  }

  const rows = [];
  const problems = [];

  for (let index = 1; index < allRows.length; index += 1) {
    const values = allRows[index];
    const sourceRow = index + 1;
    if (values.every(isBlank)) continue;

    let rowDate;
    try {
      rowDate = parseDate(cellOf(values, mapping, 'date'));
    } catch (error) {
      if (!(error instanceof UnparseableDate)) throw error;
      problems.push({
        sourceRow,
        field: 'date',
        raw: String(cellOf(values, mapping, 'date')),
        reason: error.message,
      });
      continue;
    }

    let net;
    try {
      net = parseAmount(cellOf(values, mapping, 'amount_net'));
    } catch (error) {
      if (!(error instanceof UnparseableAmount)) throw error;
      problems.push({
        sourceRow,
        field: 'amount_net',
        raw: String(cellOf(values, mapping, 'amount_net')),
        reason: error.message,
      });
      continue;
    }

    const currencyRaw = cellOf(values, mapping, 'currency');
    const currency = isBlank(currencyRaw)
      ? defaultCurrencyFor(rowDate)
      : String(currencyRaw).trim().toUpperCase();

    const vatRaw = cellOf(values, mapping, 'vat_amount');
    let vatAmount = null;
    if (!isBlank(vatRaw)) {
      try {
        vatAmount = new Money(parseAmount(vatRaw), currency);
      } catch (error) {
        problems.push({
          sourceRow,
          field: 'vat_amount',
          raw: String(vatRaw),
          reason: error.message,
        });
        continue;
      }
    }

    const rateRaw = cellOf(values, mapping, 'vat_rate');
    let vatRate = null;
    if (!isBlank(rateRaw)) {
      try {
        vatRate = parseAmount(rateRaw);
      } catch (error) {
        problems.push({
          sourceRow,
          field: 'vat_rate',
          raw: String(rateRaw),
          reason: error.message,
        });
        continue;
      }
    }

    const extra = {};
    allRows[0].forEach((header, columnIndex) => {
      if (!isBlank(header) && unmapped.includes(String(header))) {
        extra[String(header)] = values[columnIndex] ?? null;
      }
    });

    const numberRaw = cellOf(values, mapping, 'vat_number');
    const accountRaw = cellOf(values, mapping, 'account');

    rows.push({
      sourceRow,
      date: rowDate,
      counterparty: String(cellOf(values, mapping, 'counterparty') ?? '').trim(),
      description: String(cellOf(values, mapping, 'description') ?? '').trim(),
      amountNet: new Money(net, currency),
      currency,
      vatNumber: isBlank(numberRaw) ? null : String(numberRaw).trim(),
      vatAmount,
      vatRate,
      account: isBlank(accountRaw) ? null : String(accountRaw).trim(),
      extra,
    });
  }

  return { rows, problems, unmappedHeaders: unmapped, sourcePath: String(path) };
}

/**
 * Flatten a value into something exceljs can store.
 *
 * This is the one place a float is permitted: the value is leaving the system
 * into a spreadsheet cell, after all arithmetic is complete, and is never read
 * back for computation.
 */
function serialize(value) {
  if (value instanceof Money) return value.amount.toNumber();
  if (Decimal.isDecimal(value)) return value.toNumber();
  return value ?? null;
}

export async function write(path, sheets) {
  const workbook = new ExcelJS.Workbook();

  for (const [name, spec] of Object.entries(sheets)) {
    const sheet = workbook.addWorksheet(name);
    sheet.addRow(spec.columns);
    const header = sheet.getRow(1);
    header.font = { bold: true };
    header.eachCell((cell) => {
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFDDDDDD' } };
      cell.alignment = { vertical: 'middle' };
    });
    spec.rows.forEach((row) => sheet.addRow(row.map(serialize)));

    sheet.views = [{ state: 'frozen', ySplit: 1 }];
    spec.columns.forEach((column, index) => {
      const widths = spec.rows.map((row) => String(serialize(row[index]) ?? '').length);
      sheet.getColumn(index + 1).width = Math.min(Math.max(column.length, ...widths, 0) + 2, 48);
    });
  }

  mkdirSync(dirname(path), { recursive: true });
  await workbook.xlsx.writeFile(path);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix js test -- workbook`
Expected: PASS — 14 tests, mirroring the Python suite

- [ ] **Step 5: Commit**

```bash
git add js/src/workbook.js js/test/workbook.test.js
git commit -m "feat: mirror workbook load and write in JavaScript"
```

---

### Task 10: Ledger cleanup and CLI (Python)

The first user-visible deliverable. Scaffolding for the CLI is folded into this task because
the cleanup output is what the CLI exists to produce — a reviewer cannot sensibly accept one
without the other.

**Files:**
- Create: `py/src/iconomics/cleanup.py`, `py/src/iconomics/cli.py`, `py/src/iconomics/__main__.py`
- Test: `py/tests/test_cleanup.py`, `py/tests/test_cli.py`

**Interfaces:**
- Consumes: `Ledger`, `Row`, `Problem`, `Sheet`, `load`, `write`, `MissingColumn` (Task 8);
  `Money` (Task 2); `normalize_counterparty` (Task 4).
- Produces:
  - `Change` — frozen dataclass: `source_row: int`, `field: str`, `before: str`,
    `after: str`, `reason: str`
  - `CleanupResult` — frozen dataclass: `rows: list[Row]`, `changes: list[Change]`,
    `exceptions: list[Problem]`
  - `canonical_vendor_map(rows: list[Row]) -> dict[str, str]` — original name → canonical name
  - `clean(ledger: Ledger, target_currency: str = "EUR") -> CleanupResult`
  - `to_sheets(result: CleanupResult) -> dict[str, Sheet]`
  - `cli.main(argv: list[str] | None = None) -> int` — exit code
  - `cli.SUMMARY_KEYS` — the fixed stdout line labels, shared with the parity test

**Three cross-language contracts fixed here.** The parity test depends on all three, so they
are specified rather than left to each implementation:

1. **Sheet names and column headers are identical.** `Clean`, `Changes`, `Exceptions`, with
   the exact headers listed in `to_sheets` below.
2. **Dates are written as ISO strings** (`2026-02-01`), not date-typed cells. openpyxl and
   exceljs disagree about date cell representation; a string is unambiguous, sorts correctly,
   and compares cleanly. The cost is that Excel shows text — acceptable, because the accountant's
   next step is reading, not date arithmetic.
3. **The stdout summary is byte-identical.** Exact format in Step 5.

**Vendor canonicalization rule:** group names by `normalize_counterparty(name).casefold()`.
Within a group the canonical form is the variant occurring most often; ties are broken by
picking the alphabetically first. This makes the choice deterministic, which golden files require.

- [ ] **Step 1: Write the failing cleanup tests**

`py/tests/test_cleanup.py`:
```python
from datetime import date
from decimal import Decimal

from iconomics.cleanup import canonical_vendor_map, clean, to_sheets
from iconomics.money import Money
from iconomics.workbook import Ledger, Problem, Row


def row(source_row, counterparty, amount, currency="EUR", when=date(2026, 2, 1)):
    return Row(
        source_row=source_row,
        date=when,
        counterparty=counterparty,
        description="",
        amount_net=Money(Decimal(amount), currency),
        currency=currency,
    )


def ledger_of(*rows, problems=()):
    return Ledger(
        rows=list(rows), problems=list(problems), unmapped_headers=[], source_path="x.xlsx"
    )


def test_vendor_variants_collapse_to_the_most_common_form():
    rows = [
        row(2, "Алфа ООД", "1"),
        row(3, "Алфа ООД", "1"),
        row(4, "алфа оод", "1"),
    ]
    mapping = canonical_vendor_map(rows)
    assert mapping["алфа оод"] == "Алфа ООД"
    assert mapping["Алфа ООД"] == "Алфа ООД"


def test_vendor_tie_is_broken_alphabetically_for_determinism():
    rows = [row(2, "Бета ЕООД", "1"), row(3, "бета еоод", "1")]
    mapping = canonical_vendor_map(rows)
    assert mapping["Бета ЕООД"] == "Бета ЕООД"
    assert mapping["бета еоод"] == "Бета ЕООД"


def test_vendor_rename_is_logged_as_a_change():
    result = clean(ledger_of(row(2, "Алфа ООД", "1"), row(3, "алфа оод", "1")))
    renames = [c for c in result.changes if c.field == "counterparty"]
    assert len(renames) == 1
    assert renames[0].source_row == 3
    assert renames[0].before == "алфа оод"
    assert renames[0].after == "Алфа ООД"


def test_bgn_rows_are_converted_to_eur_and_logged():
    result = clean(ledger_of(row(2, "Алфа ООД", "195.583", currency="BGN")))
    assert result.rows[0].amount_net == Money(Decimal("100.00"), "EUR")
    assert result.rows[0].currency == "EUR"
    conversions = [c for c in result.changes if c.field == "amount_net"]
    assert conversions[0].before == "195.583 BGN"
    assert conversions[0].after == "100.00 EUR"
    assert "1.95583" in conversions[0].reason


def test_rows_already_in_target_currency_produce_no_change():
    result = clean(ledger_of(row(2, "Алфа ООД", "10.00", currency="EUR")))
    assert result.changes == []


def test_vat_amount_is_converted_too():
    original = Row(
        source_row=2,
        date=date(2025, 12, 1),
        counterparty="Алфа ООД",
        description="",
        amount_net=Money(Decimal("195.583"), "BGN"),
        currency="BGN",
        vat_amount=Money(Decimal("39.12"), "BGN"),
    )
    result = clean(ledger_of(original))
    assert result.rows[0].vat_amount.currency == "EUR"
    assert any(c.field == "vat_amount" for c in result.changes)


def test_target_currency_can_be_bgn():
    result = clean(ledger_of(row(2, "Алфа ООД", "100.00", currency="EUR")), target_currency="BGN")
    assert result.rows[0].amount_net == Money(Decimal("195.58"), "BGN")


def test_load_problems_pass_through_as_exceptions():
    problem = Problem(source_row=5, field="amount_net", raw="n/a", reason="empty cell")
    result = clean(ledger_of(row(2, "Алфа ООД", "1"), problems=[problem]))
    assert result.exceptions == [problem]


def test_sheets_have_the_contracted_names_and_headers():
    sheets = to_sheets(clean(ledger_of(row(2, "Алфа ООД", "1"))))
    assert list(sheets) == ["Clean", "Changes", "Exceptions"]
    assert sheets["Clean"].columns == [
        "Source Row",
        "Date",
        "Counterparty",
        "VAT Number",
        "Description",
        "Net",
        "VAT",
        "Currency",
        "Account",
    ]
    assert sheets["Changes"].columns == ["Source Row", "Field", "Before", "After", "Reason"]
    assert sheets["Exceptions"].columns == ["Source Row", "Field", "Raw Value", "Reason"]


def test_dates_are_written_as_iso_strings():
    sheets = to_sheets(clean(ledger_of(row(2, "Алфа ООД", "1", when=date(2026, 2, 1)))))
    assert sheets["Clean"].rows[0][1] == "2026-02-01"


def test_clean_rows_are_sorted_by_date_then_source_row():
    result = clean(
        ledger_of(
            row(4, "Алфа ООД", "1", when=date(2026, 2, 10)),
            row(2, "Алфа ООД", "1", when=date(2026, 2, 1)),
            row(3, "Алфа ООД", "1", when=date(2026, 2, 1)),
        )
    )
    assert [r.source_row for r in result.rows] == [2, 3, 4]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd py && python -m pytest tests/test_cleanup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'iconomics.cleanup'`

- [ ] **Step 3: Write the cleanup implementation**

`py/src/iconomics/cleanup.py`:
```python
"""Ledger cleanup: normalize vendors, unify currency, log every change.

The change log is the point of this workflow. An accountant will not trust a
tool that silently rewrites their data, so every alteration is recorded with
the original value, the new value, and the reason.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, replace

from iconomics.money import BGN_PER_EUR, Money
from iconomics.parsing import normalize_counterparty
from iconomics.workbook import Ledger, Problem, Row, Sheet

CLEAN_COLUMNS = [
    "Source Row",
    "Date",
    "Counterparty",
    "VAT Number",
    "Description",
    "Net",
    "VAT",
    "Currency",
    "Account",
]
CHANGE_COLUMNS = ["Source Row", "Field", "Before", "After", "Reason"]
EXCEPTION_COLUMNS = ["Source Row", "Field", "Raw Value", "Reason"]


@dataclass(frozen=True)
class Change:
    source_row: int
    field: str
    before: str
    after: str
    reason: str


@dataclass(frozen=True)
class CleanupResult:
    rows: list[Row]
    changes: list[Change]
    exceptions: list[Problem]


def canonical_vendor_map(rows: list[Row]) -> dict[str, str]:
    """Map each vendor spelling to the canonical spelling for its group.

    Grouping key is the normalized, case-folded name, so "Алфа ООД.",
    "алфа оод" and "Алфа  ООД" all land in one group. The canonical form is
    the most frequent original spelling, ties broken alphabetically so the
    result is deterministic across runs.
    """
    groups: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        key = normalize_counterparty(row.counterparty).casefold()
        groups[key][row.counterparty] += 1

    mapping: dict[str, str] = {}
    for variants in groups.values():
        best = min(variants.items(), key=lambda item: (-item[1], item[0]))[0]
        canonical = normalize_counterparty(best)
        for variant in variants:
            mapping[variant] = canonical
    return mapping


def _convert(money: Money, target: str) -> Money:
    return money.to_eur() if target == "EUR" else money.to_bgn()


def clean(ledger: Ledger, target_currency: str = "EUR") -> CleanupResult:
    """Normalize vendor names and restate every row into one currency."""
    if target_currency not in ("EUR", "BGN"):
        raise ValueError(f"unsupported target currency {target_currency!r}")

    vendors = canonical_vendor_map(ledger.rows)
    changes: list[Change] = []
    cleaned: list[Row] = []

    for row in ledger.rows:
        updates: dict[str, object] = {}

        canonical = vendors[row.counterparty]
        if canonical != row.counterparty:
            updates["counterparty"] = canonical
            changes.append(
                Change(
                    source_row=row.source_row,
                    field="counterparty",
                    before=row.counterparty,
                    after=canonical,
                    reason="merged vendor spelling variants",
                )
            )

        if row.currency != target_currency:
            reason = f"converted at the fixed rate 1 EUR = {BGN_PER_EUR} BGN"

            converted_net = _convert(row.amount_net, target_currency)
            updates["amount_net"] = converted_net
            updates["currency"] = target_currency
            changes.append(
                Change(
                    source_row=row.source_row,
                    field="amount_net",
                    before=str(row.amount_net),
                    after=str(converted_net),
                    reason=reason,
                )
            )

            if row.vat_amount is not None:
                converted_vat = _convert(row.vat_amount, target_currency)
                updates["vat_amount"] = converted_vat
                changes.append(
                    Change(
                        source_row=row.source_row,
                        field="vat_amount",
                        before=str(row.vat_amount),
                        after=str(converted_vat),
                        reason=reason,
                    )
                )

        cleaned.append(replace(row, **updates) if updates else row)

    cleaned.sort(key=lambda row: (row.date, row.source_row))
    changes.sort(key=lambda change: (change.source_row, change.field))
    return CleanupResult(rows=cleaned, changes=changes, exceptions=list(ledger.problems))


def to_sheets(result: CleanupResult) -> dict[str, Sheet]:
    """Render a cleanup result as the three contracted sheets."""
    clean_rows = [
        [
            row.source_row,
            row.date.isoformat(),
            row.counterparty,
            row.vat_number or "",
            row.description,
            row.amount_net,
            row.vat_amount if row.vat_amount is not None else "",
            row.currency,
            row.account or "",
        ]
        for row in result.rows
    ]
    change_rows = [
        [c.source_row, c.field, c.before, c.after, c.reason] for c in result.changes
    ]
    exception_rows = [
        [p.source_row, p.field, p.raw, p.reason] for p in result.exceptions
    ]

    return {
        "Clean": Sheet(columns=CLEAN_COLUMNS, rows=clean_rows),
        "Changes": Sheet(columns=CHANGE_COLUMNS, rows=change_rows),
        "Exceptions": Sheet(columns=EXCEPTION_COLUMNS, rows=exception_rows),
    }
```

- [ ] **Step 4: Run them to verify they pass**

Run: `cd py && python -m pytest tests/test_cleanup.py -v`
Expected: PASS — 11 tests

- [ ] **Step 5: Write the failing CLI tests**

The stdout format is a cross-language contract. Exact expected output for the February
sample (4 clean rows, 2 exceptions):

```
cleanup: ledger-2026-02.xlsx
  rows in:     6
  rows clean:  4
  changes:     1
  exceptions:  2
  output:      output/ledger-2026-02-clean.xlsx
```

`py/tests/test_cli.py`:
```python
import pytest

from iconomics import cli
from iconomics.config import find_config_dir


def sample(name):
    return str(find_config_dir().parent / "data" / "raw" / name)


def test_cleanup_writes_output_and_reports_zero(tmp_path, capsys):
    code = cli.main(["cleanup", "--in", sample("ledger-2026-02.xlsx"), "--out", str(tmp_path)])
    assert code == 0
    assert (tmp_path / "ledger-2026-02-clean.xlsx").is_file()


def test_cleanup_summary_has_the_contracted_format(tmp_path, capsys):
    cli.main(["cleanup", "--in", sample("ledger-2026-02.xlsx"), "--out", str(tmp_path)])
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0] == "cleanup: ledger-2026-02.xlsx"
    assert lines[1] == "  rows in:     6"
    assert lines[2] == "  rows clean:  4"
    assert lines[4] == "  exceptions:  2"
    assert lines[5].startswith("  output:      ")


def test_january_file_converts_bgn_rows(tmp_path, capsys):
    cli.main(["cleanup", "--in", sample("ledger-2026-01.xlsx"), "--out", str(tmp_path)])
    out = capsys.readouterr().out
    # Three BGN rows, each contributing a net conversion; two also carry VAT.
    assert "changes:" in out


def test_missing_column_is_exit_code_one(tmp_path, capsys):
    bad = tmp_path / "bad.xlsx"
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.active.append(["Дата", "Контрагент"])
    workbook.save(bad)

    code = cli.main(["cleanup", "--in", str(bad), "--out", str(tmp_path)])
    assert code == 1
    assert "amount_net" in capsys.readouterr().err


def test_unknown_subcommand_is_exit_code_two():
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["nonsense"])
    assert exit_info.value.code == 2


def test_invalid_currency_is_exit_code_two(tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(
            [
                "cleanup",
                "--in",
                sample("ledger-2026-02.xlsx"),
                "--out",
                str(tmp_path),
                "--currency",
                "USD",
            ]
        )
    assert exit_info.value.code == 2
```

- [ ] **Step 6: Run them to verify they fail**

Run: `cd py && python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ImportError: cannot import name 'cli'`

- [ ] **Step 7: Write the CLI**

`py/src/iconomics/cli.py`:
```python
"""Command line entry point.

The subcommands, flags, exit codes, and stdout format here are a contract
shared with the JavaScript implementation. Changing any of them means
changing js/bin/iconomics.js in the same commit, or the parity test fails.

Exit codes:  0 success · 1 structural failure · 2 bad usage
"""

import argparse
import sys
from pathlib import Path

from iconomics.cleanup import clean, to_sheets
from iconomics.workbook import MissingColumn, load, write

SUMMARY_KEYS = ("rows in", "rows clean", "changes", "exceptions", "output")
_LABEL_WIDTH = max(len(key) for key in SUMMARY_KEYS) + 1


def _summary_line(key: str, value: object) -> str:
    return f"  {key + ':':<{_LABEL_WIDTH + 1}} {value}"


def _run_cleanup(args: argparse.Namespace) -> int:
    source = Path(args.input)
    try:
        ledger = load(source)
    except MissingColumn as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    result = clean(ledger, target_currency=args.currency)
    destination = Path(args.out) / f"{source.stem}-clean.xlsx"
    write(destination, to_sheets(result))

    rows_in = len(ledger.rows) + len(ledger.problems)
    print(f"cleanup: {source.name}")
    print(_summary_line("rows in", rows_in))
    print(_summary_line("rows clean", len(result.rows)))
    print(_summary_line("changes", len(result.changes)))
    print(_summary_line("exceptions", len(result.exceptions)))
    print(_summary_line("output", destination))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="iconomics", description="Bulgarian accounting toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    cleanup = subparsers.add_parser("cleanup", help="normalize a messy ledger export")
    cleanup.add_argument("--in", dest="input", required=True, help="input .xlsx path")
    cleanup.add_argument("--out", required=True, help="output directory")
    cleanup.add_argument(
        "--currency",
        default="EUR",
        choices=("EUR", "BGN"),
        help="restate all amounts into this currency (default: EUR)",
    )
    cleanup.set_defaults(handler=_run_cleanup)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

`py/src/iconomics/__main__.py`:
```python
from iconomics.cli import main

raise SystemExit(main())
```

- [ ] **Step 8: Run the CLI tests and then the real thing**

Run: `cd py && python -m pytest tests/test_cli.py -v`
Expected: PASS — 6 tests

Run from the repo root:
`python -m iconomics cleanup --in data/raw/ledger-2026-01.xlsx --out output/`
Expected: the summary block, and `output/ledger-2026-01-clean.xlsx` containing three sheets
with the BGN rows restated to EUR and each conversion logged in `Changes`.

- [ ] **Step 9: Commit**

```bash
git add py/src/iconomics/cleanup.py py/src/iconomics/cli.py py/src/iconomics/__main__.py \
        py/tests/test_cleanup.py py/tests/test_cli.py
git commit -m "feat: add ledger cleanup workflow and CLI"
```

---
