/**
 * Money arithmetic and the fixed BGN/EUR conversion.
 *
 * Bulgaria adopted the euro on 2026-01-01 at an irrevocable rate of
 * 1 EUR = 1.95583 BGN. The rate is a constant, not a configuration value.
 *
 * The rounding mode is passed explicitly on every quantize rather than relying
 * on the decimal.js global default, so q2 matches Python's ROUND_HALF_UP even
 * if another module changes Decimal's configuration.
 */

import Decimal from 'decimal.js';

export const BGN_PER_EUR = new Decimal('1.95583');
export const EURO_START = new Date(Date.UTC(2026, 0, 1));
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

  /**
   * Match Python's `str(Money)` exactly — the cleanup change log embeds this
   * string, and the parity test compares those cells.
   *
   * Python's Decimal preserves the scale it was constructed with, so
   * Decimal("195.583") prints "195.583" and Decimal("100.00") prints "100.00".
   * decimal.js normalizes away trailing zeros, so a plain toString() would
   * print "100". toFixed() with the recorded scale reproduces Python's output.
   */
  toString() {
    return `${this.amount.toFixed(this.scale())} ${this.currency}`;
  }

  /** Decimal places to render: at least 2, more if the value genuinely has them. */
  scale() {
    return Math.max(2, this.amount.decimalPlaces());
  }
}

/** The currency a transaction is presumed to be in, absent an explicit one. */
export function defaultCurrencyFor(when) {
  return when.getTime() >= EURO_START.getTime() ? 'EUR' : 'BGN';
}
