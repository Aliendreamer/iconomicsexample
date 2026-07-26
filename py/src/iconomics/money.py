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
