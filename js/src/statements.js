/**
 * Trial balance -> profit and loss, balance sheet, and comparatives.
 * Mirrors py/src/iconomics/statements.py.
 *
 * All internal arithmetic is debit-positive (debit - credit). Aggregating in each
 * account's natural direction would break any statement line fed by accounts with
 * opposite normal sides — a receivable and a payable rolling into one line would
 * add rather than offset. Direction is applied only for presentation.
 *
 * No statutory cash flow statement is produced. See CASH_NOTE.
 */

import Decimal from 'decimal.js';

import { BALANCE_SHEET, PROFIT_AND_LOSS, lineSide, loadCoa } from './coa.js';
import { Money } from './money.js';

export const PNL_COLUMNS = ['Line', 'Current Period', 'Prior Period', 'Change'];
export const BS_COLUMNS = ['Line', 'Section', 'Current Period', 'Prior Period', 'Change'];
export const CASH_COLUMNS = ['Account', 'Name', 'Opening', 'Closing', 'Movement'];
export const UNMAPPED_COLUMNS = ['Source Row', 'Account', 'Reason'];
export const CHECK_COLUMNS = ['Check', 'Result', 'Detail'];

export const MONEY_FORMATS = {
  'Current Period': '0.00',
  'Prior Period': '0.00',
  Change: '0.00',
  Opening: '0.00',
  Closing: '0.00',
  Movement: '0.00',
};

export const CASH_NOTE =
  'Cash movement summary — NOT a statutory cash flow statement. Derived from ' +
  'the change in cash account balances between the two trial balances supplied. ' +
  'A statutory statement requires movement analysis.';

export const RESULT_LINE = 'Финансов резултат за периода';
export const ASSETS_LINE = 'Общо активи';
export const EQUITY_LIABILITIES_LINE = 'Общо собствен капитал и задължения';

export class Unbalanced extends Error {}

const zero = (currency) => new Money(new Decimal('0.00'), currency);

/**
 * Convert every balance to the target currency at the fixed rate. This is how a
 * 2025 BGN trial balance becomes usable as a comparative against 2026 EUR
 * figures. Conversion is from the originally recorded amount, never chained.
 */
export function restateTrialBalance(balance, targetCurrency) {
  const convert = (m) => (targetCurrency === 'EUR' ? m.toEur() : m.toBgn());
  return {
    lines: balance.lines.map((line) => ({
      sourceRow: line.sourceRow,
      account: line.account,
      name: line.name,
      debit: convert(line.debit),
      credit: convert(line.credit),
    })),
    problems: [...balance.problems],
    sourcePath: balance.sourcePath,
  };
}

function totalsOf(balance, currency) {
  let debits = zero(currency);
  let credits = zero(currency);
  for (const line of balance.lines) {
    debits = debits.add(line.debit);
    credits = credits.add(line.credit);
  }
  return { debits, credits };
}

function rollUp(balance, coa, currency) {
  const pnl = {};
  const bs = {};
  const cash = [];
  const unmapped = [];

  for (const line of balance.lines) {
    const account = coa.get(line.account);
    if (account === null) {
      unmapped.push({
        sourceRow: line.sourceRow,
        field: 'account',
        raw: line.account,
        reason: 'not in config/coa.yaml; add it or correct the code',
      });
      continue;
    }

    const signed = line.debit.sub(line.credit);
    const target = account.statement === PROFIT_AND_LOSS ? pnl : bs;
    target[account.line] = (target[account.line] ?? zero(currency)).add(signed);

    if (account.cash) {
      cash.push([account.code, account.name || line.name, line.debit, line.credit]);
    }
  }

  return { pnl, bs, cash, unmapped };
}

/** Flip credit-natured lines so revenue and liabilities read positive. */
function display(lineName, signed, coa) {
  return lineSide(lineName, coa) === 'credit'
    ? zero(signed.currency).sub(signed)
    : signed;
}

/**
 * Revenue less expenses. Debit-positive means expenses are positive and revenue
 * negative, so the period result is the negated sum.
 */
function resultFrom(pnl, currency) {
  let total = zero(currency);
  for (const amount of Object.values(pnl)) total = total.add(amount);
  return zero(currency).sub(total);
}

function pairCash(current, prior, currency) {
  const priorByCode = {};
  for (const [code, , debit, credit] of prior) priorByCode[code] = debit.sub(credit);
  return [...current]
    .sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))
    .map(([code, name, debit, credit]) => [
      code,
      name,
      priorByCode[code] ?? zero(currency),
      debit.sub(credit),
    ]);
}

export function build(current, prior = null, currency = 'EUR') {
  const coa = loadCoa();

  const { debits, credits } = totalsOf(current, currency);
  if (!debits.equals(credits)) {
    throw new Unbalanced(
      `trial balance does not balance: debits ${debits} vs credits ${credits}. ` +
        'Nothing was written — a half-correct statement is worse than none.',
    );
  }

  const { pnl, bs, cash: cashLines, unmapped } = rollUp(current, coa, currency);
  const result = resultFrom(pnl, currency);

  let priorPnl = {};
  let priorBs = {};
  let priorCash = [];
  let priorResult = zero(currency);

  if (prior !== null) {
    const priorTotals = totalsOf(prior, currency);
    if (!priorTotals.debits.equals(priorTotals.credits)) {
      throw new Unbalanced(
        `prior trial balance does not balance: debits ${priorTotals.debits} vs ` +
          `credits ${priorTotals.credits}`,
      );
    }
    const rolled = rollUp(prior, coa, currency);
    priorPnl = rolled.pnl;
    priorBs = rolled.bs;
    priorCash = rolled.cash;
    priorResult = resultFrom(priorPnl, currency);
  }

  let assets = zero(currency);
  let equityAndLiabilities = zero(currency);
  for (const [lineName, signed] of Object.entries(bs)) {
    if (lineSide(lineName, coa) === 'debit') {
      assets = assets.add(signed);
    } else {
      equityAndLiabilities = equityAndLiabilities.add(zero(currency).sub(signed));
    }
  }

  const balances = assets.equals(equityAndLiabilities.add(result));
  if (!balances) {
    throw new Unbalanced(
      `balance sheet does not balance: assets ${assets} vs equity and ` +
        `liabilities ${equityAndLiabilities} plus result ${result} ` +
        `(difference ${assets.sub(equityAndLiabilities).sub(result)}). ` +
        'This usually means an account is mapped to the wrong statement or ' +
        'side in config/coa.yaml. Nothing was written.',
    );
  }

  return {
    pnl,
    balanceSheet: bs,
    priorPnl,
    priorBalanceSheet: priorBs,
    cash: pairCash(cashLines, priorCash, currency),
    unmapped,
    result,
    priorResult,
    assets,
    equityAndLiabilities,
    currency,
    coa,
    hasPrior: prior !== null,
    checks: { trial_balance_balances: true, balance_sheet_balances: balances },
  };
}

function orderedNames(current, prior, ordered) {
  const present = new Set([...Object.keys(current), ...Object.keys(prior)]);
  const names = ordered.filter((name) => present.has(name));
  const rest = [...present].filter((name) => !names.includes(name)).sort();
  return [...names, ...rest];
}

export function toSheets(result) {
  const rowsFor = (current, prior, ordered, withSection = false) =>
    orderedNames(current, prior, ordered).map((name) => {
      const now = display(name, current[name] ?? zero(result.currency), result.coa);
      const was = display(name, prior[name] ?? zero(result.currency), result.coa);
      const cells = [name];
      if (withSection) {
        cells.push(
          lineSide(name, result.coa) === 'debit'
            ? 'Активи'
            : 'Собствен капитал и задължения',
        );
      }
      cells.push(now, result.hasPrior ? was : null, result.hasPrior ? now.sub(was) : null);
      return cells;
    });

  const pnlRows = rowsFor(result.pnl, result.priorPnl, result.coa.orderedLines(PROFIT_AND_LOSS));
  pnlRows.push([
    RESULT_LINE,
    result.result,
    result.hasPrior ? result.priorResult : null,
    result.hasPrior ? result.result.sub(result.priorResult) : null,
  ]);

  const bsRows = rowsFor(
    result.balanceSheet,
    result.priorBalanceSheet,
    result.coa.orderedLines(BALANCE_SHEET),
    true,
  );
  bsRows.push([RESULT_LINE, 'Собствен капитал и задължения', result.result, null, null]);
  bsRows.push([ASSETS_LINE, 'Активи', result.assets, null, null]);
  bsRows.push([
    EQUITY_LIABILITIES_LINE,
    'Собствен капитал и задължения',
    result.equityAndLiabilities.add(result.result),
    null,
    null,
  ]);

  const checkRows = [
    [
      'Trial balance balances (debits = credits)',
      result.checks.trial_balance_balances ? 'yes' : 'NO',
      'checked before any output was written',
    ],
    [
      'Balance sheet balances (assets = equity + liabilities + result)',
      result.checks.balance_sheet_balances ? 'yes' : 'NO',
      `${result.assets} = ${result.equityAndLiabilities} + ${result.result}`,
    ],
    [
      'Comparatives included',
      result.hasPrior ? 'yes' : 'no',
      'supply --prior to add a comparative column',
    ],
    ['Cash flow statement', 'no', CASH_NOTE],
  ];

  const sheets = {
    ОПР: { columns: PNL_COLUMNS, rows: pnlRows, numberFormats: MONEY_FORMATS },
    Баланс: { columns: BS_COLUMNS, rows: bsRows, numberFormats: MONEY_FORMATS },
    Checks: { columns: CHECK_COLUMNS, rows: checkRows },
  };

  if (result.hasPrior) {
    sheets['Парични средства'] = {
      columns: CASH_COLUMNS,
      rows: result.cash.map(([code, name, opening, closing]) => [
        code,
        name,
        opening,
        closing,
        closing.sub(opening),
      ]),
      numberFormats: MONEY_FORMATS,
    };
  }

  if (result.unmapped.length > 0) {
    sheets['Unmapped Accounts'] = {
      columns: UNMAPPED_COLUMNS,
      rows: result.unmapped.map((p) => [p.sourceRow, p.raw, p.reason]),
    };
  }

  return sheets;
}
