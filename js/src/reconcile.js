/**
 * Bank reconciliation: match statement lines against ledger entries.
 * Mirrors py/src/iconomics/reconcile.py.
 *
 * Only `exact` is presented as settled. Everything else is a proposal for a
 * human, because a wrong match hides a real discrepancy — the exact failure a
 * reconciliation exists to catch.
 *
 * Matching is greedy but deterministic: candidates are considered in date then
 * row order, each row is consumed at most once, so the same inputs always
 * produce the same pairing.
 */

import Decimal from 'decimal.js';

import { Money } from './money.js';
import { isoDay, normalizeCounterparty } from './parsing.js';

export const EXACT = 'exact';
export const PROBABLE = 'probable';
export const POSSIBLE = 'possible';

export const MATCHED_COLUMNS = [
  'Tier',
  'Statement Row',
  'Statement Date',
  'Statement Narration',
  'Ledger Row',
  'Ledger Date',
  'Counterparty',
  'Amount',
  'Day Gap',
];
export const UNMATCHED_STATEMENT_COLUMNS = [
  'Statement Row',
  'Date',
  'Narration',
  'Amount',
  'Reason',
];
export const UNMATCHED_LEDGER_COLUMNS = [
  'Ledger Row',
  'Date',
  'Counterparty',
  'Amount',
  'Reason',
];
export const SUMMARY_COLUMNS = ['Measure', 'Count', 'Value'];

export const MONEY_FORMATS = { Amount: '0.00', Value: '0.00' };

/** Bank value dates commonly lag the invoice date by a few days. */
export const DEFAULT_WINDOW = 5;

const MS_PER_DAY = 86400000;
const zero = (currency) => new Money(new Decimal('0.00'), currency);

/** A statement line's text: its description, or its counterparty column. */
function narration(row) {
  return [row.description ?? '', row.counterparty ?? '']
    .filter((part) => part)
    .join(' ')
    .trim();
}

/** Whether the ledger counterparty is recognisable in the statement text. */
function counterpartyAppears(ledgerRow, statementRow) {
  const name = normalizeCounterparty(ledgerRow.counterparty ?? '').toLowerCase();
  if (!name) return false;
  const haystack = normalizeCounterparty(narration(statementRow)).toLowerCase();
  if (!haystack) return false;
  if (haystack.includes(name)) return true;
  // Bank narration often truncates "Алфа ООД" to "АЛФА" or appends a reference.
  const head = name.split(' ')[0];
  return head.length >= 3 && haystack.includes(head);
}

function tierOf(ledgerRow, statementRow, window) {
  if (!ledgerRow.amountNet.equals(statementRow.amountNet)) return null;

  const gap = Math.abs(Math.round((statementRow.date - ledgerRow.date) / MS_PER_DAY));
  const named = counterpartyAppears(ledgerRow, statementRow);

  if (gap === 0 && named) return [EXACT, gap];
  if (gap <= window && named) return [PROBABLE, gap];
  if (gap <= window) return [POSSIBLE, gap];
  return null;
}

/**
 * Put every row into one currency so amounts are comparable. Real March 2026
 * data still contains BGN correction entries, and an amount cannot be matched
 * across currencies. The count is reported so the run does not quietly change
 * figures.
 */
function restate(rows, currency) {
  let changed = 0;
  const restated = rows.map((row) => {
    if (row.currency === currency) return row;
    const convert = (m) => (currency === 'EUR' ? m.toEur() : m.toBgn());
    changed += 1;
    return {
      ...row,
      amountNet: convert(row.amountNet),
      vatAmount: row.vatAmount ? convert(row.vatAmount) : null,
      currency,
    };
  });
  return { rows: restated, changed };
}

const byDateThenRow = (a, b) => a.date - b.date || a.sourceRow - b.sourceRow;

export function reconcile(statement, ledger, window = DEFAULT_WINDOW, currency = 'EUR') {
  const restatedStatement = restate(statement.rows, currency);
  const restatedLedger = restate(ledger.rows, currency);
  const restated = restatedStatement.changed + restatedLedger.changed;

  const statementRows = [...restatedStatement.rows].sort(byDateThenRow);
  const ledgerRows = [...restatedLedger.rows].sort(byDateThenRow);

  const usedLedger = new Set();
  const matched = [];

  // Best tier first, so a clean pairing is never stolen by a weaker candidate.
  for (const tier of [EXACT, PROBABLE, POSSIBLE]) {
    for (const statementRow of statementRows) {
      if (matched.some((m) => m.statement.sourceRow === statementRow.sourceRow)) continue;
      for (const ledgerRow of ledgerRows) {
        if (usedLedger.has(ledgerRow.sourceRow)) continue;
        const verdict = tierOf(ledgerRow, statementRow, window);
        if (verdict === null || verdict[0] !== tier) continue;
        matched.push({
          tier,
          statement: statementRow,
          ledger: ledgerRow,
          dayGap: verdict[1],
        });
        usedLedger.add(ledgerRow.sourceRow);
        break;
      }
    }
  }

  const matchedStatementRows = new Set(matched.map((m) => m.statement.sourceRow));
  const unmatchedStatement = statementRows.filter(
    (row) => !matchedStatementRows.has(row.sourceRow),
  );
  const unmatchedLedger = ledgerRows.filter((row) => !usedLedger.has(row.sourceRow));

  matched.sort(
    (a, b) => a.statement.date - b.statement.date || a.statement.sourceRow - b.statement.sourceRow,
  );

  return {
    matched,
    unmatchedStatement,
    unmatchedLedger,
    currency,
    window,
    restated,
    get confirmed() {
      return this.matched.filter((m) => m.tier === EXACT);
    },
    get proposed() {
      return this.matched.filter((m) => m.tier !== EXACT);
    },
  };
}

function totalOf(rows, currency) {
  let total = zero(currency);
  for (const row of rows) total = total.add(row.amountNet);
  return total;
}

export function toSheets(result) {
  const matchRows = (matches) =>
    matches.map((m) => [
      m.tier,
      m.statement.sourceRow,
      isoDay(m.statement.date),
      narration(m.statement),
      m.ledger.sourceRow,
      isoDay(m.ledger.date),
      m.ledger.counterparty,
      m.ledger.amountNet,
      m.dayGap,
    ]);

  const confirmed = result.confirmed;
  const proposed = result.proposed;

  const summaryRows = [
    [
      'Statement lines matched (confirmed)',
      confirmed.length,
      totalOf(
        confirmed.map((m) => m.statement),
        result.currency,
      ),
    ],
    [
      'Statement lines proposed (review)',
      proposed.length,
      totalOf(
        proposed.map((m) => m.statement),
        result.currency,
      ),
    ],
    [
      'Statement lines unmatched',
      result.unmatchedStatement.length,
      totalOf(result.unmatchedStatement, result.currency),
    ],
    [
      'Ledger rows unmatched',
      result.unmatchedLedger.length,
      totalOf(result.unmatchedLedger, result.currency),
    ],
    ['Date window used (days)', result.window, ''],
    [`Rows restated to ${result.currency}`, result.restated, ''],
  ];

  return {
    Matched: {
      columns: MATCHED_COLUMNS,
      rows: matchRows(confirmed),
      numberFormats: MONEY_FORMATS,
    },
    Proposed: {
      columns: MATCHED_COLUMNS,
      rows: matchRows(proposed),
      numberFormats: MONEY_FORMATS,
    },
    'Unmatched Statement': {
      columns: UNMATCHED_STATEMENT_COLUMNS,
      rows: result.unmatchedStatement.map((row) => [
        row.sourceRow,
        isoDay(row.date),
        narration(row),
        row.amountNet,
        'no ledger entry with this amount in the date window',
      ]),
      numberFormats: MONEY_FORMATS,
    },
    'Unmatched Ledger': {
      columns: UNMATCHED_LEDGER_COLUMNS,
      rows: result.unmatchedLedger.map((row) => [
        row.sourceRow,
        isoDay(row.date),
        row.counterparty,
        row.amountNet,
        'not seen on the bank statement',
      ]),
      numberFormats: MONEY_FORMATS,
    },
    Summary: {
      columns: SUMMARY_COLUMNS,
      rows: summaryRows,
      numberFormats: { Value: '0.00' },
    },
  };
}
