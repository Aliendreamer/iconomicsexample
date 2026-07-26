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
  jan: 1,
  feb: 2,
  mar: 3,
  apr: 4,
  may: 5,
  jun: 6,
  jul: 7,
  aug: 8,
  sep: 9,
  oct: 10,
  nov: 11,
  dec: 12,
};

export class UnparseableAmount extends Error {}
export class UnparseableDate extends Error {}

export function fromExcelSerial(serial) {
  return new Date(EXCEL_EPOCH_UTC + Math.trunc(serial) * MS_PER_DAY);
}

/**
 * Normalize a numeric string to use '.' as the decimal separator.
 *
 * Bulgarian exports use comma as the decimal separator and space or dot for
 * thousands; English-locale exports do the opposite. Resolution order:
 *   1. both separators present -> the rightmost is the decimal one
 *   2. one separator, 1-2 digits after -> decimal separator
 *   3. one separator, exactly 3 digits after -> thousands separator
 *   4. anything else -> unparseable
 */
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
    const digitsAfter = text.length - text.lastIndexOf(sep) - 1;
    if (digitsAfter === 1 || digitsAfter === 2) return text.replace(sep, '.');
    if (digitsAfter === 3) return text.replace(sep, '');
    throw new UnparseableAmount(`ambiguous separators in '${text}'`);
  }

  return text;
}

export function parseAmount(raw) {
  if (raw === null || raw === undefined) throw new UnparseableAmount('empty cell');
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
  const built = new Date(Date.UTC(year, month - 1, day));
  // Reject overflow, so 32.01 does not silently roll into February.
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

  // Bulgarian dd.mm.yyyy and dd/mm/yyyy — day first
  match = text.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})$/);
  if (match) {
    let year = Number(match[3]);
    if (year < 100) year += 2000;
    return utcDate(year, Number(match[2]), Number(match[1]));
  }

  throw new UnparseableDate(`cannot read date from '${text}'`);
}

export function parseDate(raw) {
  if (raw === null || raw === undefined) throw new UnparseableDate('empty cell');
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

/** Format a parsed date as the ISO day string used in output sheets. */
export function isoDay(when) {
  return when.toISOString().slice(0, 10);
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
