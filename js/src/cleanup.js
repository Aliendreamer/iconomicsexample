/**
 * Ledger cleanup: normalize vendors, unify currency, log every change.
 * Mirrors py/src/iconomics/cleanup.py.
 *
 * The change log is the point of this workflow. An accountant will not trust a
 * tool that silently rewrites their data, so every alteration is recorded with
 * the original value, the new value, and the reason.
 */

import { BGN_PER_EUR } from './money.js';
import { isoDay, normalizeCounterparty } from './parsing.js';

export const CLEAN_COLUMNS = [
  'Source Row',
  'Date',
  'Counterparty',
  'VAT Number',
  'Description',
  'Net',
  'VAT',
  'Currency',
  'Account',
];
export const CHANGE_COLUMNS = ['Source Row', 'Field', 'Before', 'After', 'Reason'];
export const EXCEPTION_COLUMNS = ['Source Row', 'Field', 'Raw Value', 'Reason'];

/**
 * Money columns get two forced decimals. Without this, Excel renders 410.00 as
 * "410", which reads as sloppy on a document an accountant hands to a client.
 */
export const MONEY_FORMATS = { Net: '0.00', VAT: '0.00' };

/**
 * Map each vendor spelling to the canonical spelling for its group.
 *
 * Grouping key is the normalized, case-folded name, so "Алфа ООД.",
 * "алфа оод" and "Алфа  ООД" all land in one group. The canonical form is the
 * most frequent original spelling, ties broken alphabetically so the result is
 * deterministic across runs.
 */
export function canonicalVendorMap(rows) {
  const groups = new Map();
  for (const row of rows) {
    const key = normalizeCounterparty(row.counterparty).toLowerCase();
    if (!groups.has(key)) groups.set(key, new Map());
    const variants = groups.get(key);
    variants.set(row.counterparty, (variants.get(row.counterparty) ?? 0) + 1);
  }

  const mapping = {};
  for (const variants of groups.values()) {
    const best = [...variants.entries()].sort(
      (a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0),
    )[0][0];
    const canonical = normalizeCounterparty(best);
    for (const variant of variants.keys()) mapping[variant] = canonical;
  }
  return mapping;
}

const convert = (money, target) => (target === 'EUR' ? money.toEur() : money.toBgn());

/** Normalize vendor names and restate every row into one currency. */
export function clean(ledger, targetCurrency = 'EUR') {
  if (targetCurrency !== 'EUR' && targetCurrency !== 'BGN') {
    throw new Error(`unsupported target currency '${targetCurrency}'`);
  }

  const vendors = canonicalVendorMap(ledger.rows);
  const changes = [];
  const cleaned = [];

  for (const row of ledger.rows) {
    const updated = { ...row };

    const canonical = vendors[row.counterparty];
    if (canonical !== row.counterparty) {
      updated.counterparty = canonical;
      changes.push({
        sourceRow: row.sourceRow,
        field: 'counterparty',
        before: row.counterparty,
        after: canonical,
        reason: 'merged vendor spelling variants',
      });
    }

    if (row.currency !== targetCurrency) {
      const reason = `converted at the fixed rate 1 EUR = ${BGN_PER_EUR.toString()} BGN`;

      const convertedNet = convert(row.amountNet, targetCurrency);
      updated.amountNet = convertedNet;
      updated.currency = targetCurrency;
      changes.push({
        sourceRow: row.sourceRow,
        field: 'amount_net',
        before: row.amountNet.toString(),
        after: convertedNet.toString(),
        reason,
      });

      if (row.vatAmount !== null) {
        const convertedVat = convert(row.vatAmount, targetCurrency);
        updated.vatAmount = convertedVat;
        changes.push({
          sourceRow: row.sourceRow,
          field: 'vat_amount',
          before: row.vatAmount.toString(),
          after: convertedVat.toString(),
          reason,
        });
      }
    }

    cleaned.push(updated);
  }

  cleaned.sort((a, b) => a.date - b.date || a.sourceRow - b.sourceRow);
  changes.sort(
    (a, b) =>
      a.sourceRow - b.sourceRow ||
      (a.field < b.field ? -1 : a.field > b.field ? 1 : 0),
  );

  return { rows: cleaned, changes, exceptions: [...ledger.problems] };
}

/**
 * Render a cleanup result as the three contracted sheets.
 *
 * Dates are written as ISO strings rather than date-typed cells: openpyxl and
 * exceljs disagree about date cell representation, and a string is unambiguous,
 * sorts correctly, and compares cleanly across the two.
 */
export function toSheets(result) {
  const cleanRows = result.rows.map((row) => [
    row.sourceRow,
    isoDay(row.date),
    row.counterparty,
    row.vatNumber ?? '',
    row.description,
    row.amountNet,
    row.vatAmount ?? '',
    row.currency,
    row.account ?? '',
  ]);
  const changeRows = result.changes.map((c) => [
    c.sourceRow,
    c.field,
    c.before,
    c.after,
    c.reason,
  ]);
  const exceptionRows = result.exceptions.map((p) => [
    p.sourceRow,
    p.field,
    p.raw,
    p.reason,
  ]);

  return {
    Clean: { columns: CLEAN_COLUMNS, rows: cleanRows, numberFormats: MONEY_FORMATS },
    Changes: { columns: CHANGE_COLUMNS, rows: changeRows },
    Exceptions: { columns: EXCEPTION_COLUMNS, rows: exceptionRows },
  };
}
