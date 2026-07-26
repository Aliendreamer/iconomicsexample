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


def test_subtraction_of_same_currency():
    assert Money(Decimal("3.03"), "EUR") - Money(Decimal("1.01"), "EUR") == Money(
        Decimal("2.02"), "EUR"
    )


def test_unknown_currency_is_rejected():
    with pytest.raises(ValueError):
        Money(Decimal("1.00"), "USD")


def test_currency_default_follows_euro_adoption():
    assert default_currency_for(date(2025, 12, 31)) == "BGN"
    assert default_currency_for(date(2026, 1, 1)) == "EUR"
    assert default_currency_for(date(2026, 7, 26)) == "EUR"


def test_str_shows_amount_and_currency():
    assert str(Money(Decimal("12.34"), "EUR")) == "12.34 EUR"
