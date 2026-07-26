#!/usr/bin/env node
/**
 * Command line entry point.
 *
 * The subcommands, flags, exit codes, and stdout format here are a contract
 * shared with the Python implementation. Changing any of them means changing
 * py/src/iconomics/cli.py in the same commit, or the parity test fails.
 *
 * Exit codes:  0 success · 1 structural failure · 2 bad usage
 */

import { parseArgs } from 'node:util';
import { basename, extname, join } from 'node:path';

import { clean, toSheets } from '../src/cleanup.js';
import { CoaError } from '../src/coa.js';
import { COMPLEXITIES, BadComplexity, build, describe } from '../src/generate.js';
import * as reconcileModule from '../src/reconcile.js';
import * as statementsModule from '../src/statements.js';
import * as vatModule from '../src/vat.js';
import {
  STATEMENT_FIELDS,
  MissingColumn,
  load,
  loadTrialBalance,
  write,
} from '../src/workbook.js';

export const SUMMARY_KEYS = ['rows in', 'rows clean', 'changes', 'exceptions', 'output'];
const LABEL_WIDTH = Math.max(...SUMMARY_KEYS.map((key) => key.length)) + 2;

function summaryLine(key, value) {
  return `  ${`${key}:`.padEnd(LABEL_WIDTH)} ${value}`;
}

const USAGE = `usage: iconomics <command> [options]

Bulgarian accounting toolkit

commands:
  cleanup      normalize a messy ledger export
               --in <file.xlsx> --out <dir> [--currency EUR|BGN]
  generate     generate a sample ledger export
               --out <file.xlsx> [--rows N] [--complexity clean|messy|nasty]
               [--period YYYY-MM]
  vat-return   build the VAT journals, declaration and VIES list
               --in <file.xlsx> --out <dir> [--currency EUR|BGN]
  statements   roll a trial balance into P&L and balance sheet
               --in <file.xlsx> --out <dir> [--prior <file.xlsx>]
               [--prior-currency EUR|BGN] [--currency EUR|BGN]
  reconcile    match a bank statement against a ledger
               --bank <file.xlsx> --ledger <file.xlsx> --out <dir>
               [--window N] [--currency EUR|BGN]
`;

function fail(message) {
  process.stderr.write(`${message}\n`);
  return 2;
}

async function runCleanup(argv) {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      options: {
        in: { type: 'string' },
        out: { type: 'string' },
        currency: { type: 'string', default: 'EUR' },
      },
      strict: true,
    });
  } catch (error) {
    return fail(`error: ${error.message}`);
  }

  const { in: input, out, currency } = parsed.values;
  if (!input) return fail('error: --in is required');
  if (!out) return fail('error: --out is required');
  if (currency !== 'EUR' && currency !== 'BGN') {
    return fail(`error: --currency must be EUR or BGN, got '${currency}'`);
  }

  let ledger;
  try {
    ledger = await load(input);
  } catch (error) {
    if (error instanceof MissingColumn) {
      process.stderr.write(`error: ${error.message}\n`);
      return 1;
    }
    throw error;
  }

  const result = clean(ledger, currency);
  const stem = basename(input, extname(input));
  const destination = join(out, `${stem}-clean.xlsx`);
  await write(destination, toSheets(result));

  const rowsIn = ledger.rows.length + ledger.problems.length;
  const lines = [
    `cleanup: ${basename(input)}`,
    summaryLine('rows in', rowsIn),
    summaryLine('rows clean', result.rows.length),
    summaryLine('changes', result.changes.length),
    summaryLine('exceptions', result.exceptions.length),
    summaryLine('output', destination),
  ];
  process.stdout.write(`${lines.join('\n')}\n`);
  return 0;
}

function parsePeriod(text) {
  const parts = text.split('-');
  if (parts.length !== 2) throw new Error(`period must look like 2026-03, got '${text}'`);
  const year = Number(parts[0]);
  const month = Number(parts[1]);
  if (!Number.isInteger(year) || !Number.isInteger(month)) {
    throw new Error(`period must look like 2026-03, got '${text}'`);
  }
  if (month < 1 || month > 12) throw new Error(`month must be 1-12, got ${month}`);
  return { year, month };
}

async function runGenerate(argv) {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      options: {
        rows: { type: 'string', default: '20' },
        complexity: { type: 'string', default: 'messy' },
        period: { type: 'string', default: '2026-03' },
        out: { type: 'string' },
      },
      strict: true,
    });
  } catch (error) {
    return fail(`error: ${error.message}`);
  }

  const { rows, complexity, period, out } = parsed.values;
  if (!out) return fail('error: --out is required');
  if (!COMPLEXITIES.includes(complexity)) {
    return fail(
      `error: --complexity must be one of ${COMPLEXITIES.join(', ')}, got '${complexity}'`,
    );
  }

  const rowCount = Number(rows);
  if (!Number.isInteger(rowCount)) return fail(`error: --rows must be a whole number`);

  let year;
  let month;
  try {
    ({ year, month } = parsePeriod(period));
  } catch (error) {
    return fail(`error: ${error.message}`);
  }

  const spec = { rows: rowCount, complexity, year, month };
  let sheet;
  try {
    sheet = build(spec);
  } catch (error) {
    if (error instanceof BadComplexity || error instanceof Error) {
      process.stderr.write(`error: ${error.message}\n`);
      return 1;
    }
    throw error;
  }

  await write(out, { Ledger: sheet });

  const lines = [`generate: ${basename(out)}`];
  for (const entry of describe(spec, sheet)) {
    const separator = entry.indexOf(': ');
    lines.push(summaryLine(entry.slice(0, separator), entry.slice(separator + 2)));
  }
  lines.push(summaryLine('output', out));
  process.stdout.write(`${lines.join('\n')}\n`);
  return 0;
}

function parseCurrency(value) {
  if (value !== 'EUR' && value !== 'BGN') {
    throw new Error(`--currency must be EUR or BGN, got '${value}'`);
  }
  return value;
}

async function runVatReturn(argv) {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      options: {
        in: { type: 'string' },
        out: { type: 'string' },
        currency: { type: 'string', default: 'EUR' },
      },
      strict: true,
    });
  } catch (error) {
    return fail(`error: ${error.message}`);
  }

  const { in: input, out, currency } = parsed.values;
  if (!input) return fail('error: --in is required');
  if (!out) return fail('error: --out is required');
  try {
    parseCurrency(currency);
  } catch (error) {
    return fail(`error: ${error.message}`);
  }

  let result;
  try {
    const ledger = await load(input);
    result = vatModule.buildReturn(ledger, currency);
  } catch (error) {
    if (error instanceof MissingColumn || error instanceof vatModule.VatConfigError) {
      process.stderr.write(`error: ${error.message}\n`);
      return 1;
    }
    throw error;
  }

  const destination = join(out, `${basename(input, extname(input))}-vat-return.xlsx`);
  await write(destination, vatModule.toSheets(result));

  const lines = [
    `vat-return: ${basename(input)}`,
    summaryLine('sales rows', result.sales.length),
    summaryLine('purchase rows', result.purchases.length),
    summaryLine('vies rows', result.vies.length),
    summaryLine('output vat', result.totals.vat_output),
    summaryLine('input vat', result.totals.vat_input),
    summaryLine('vat payable', result.totals.vat_net),
    summaryLine('unclassified', result.unclassified.length),
    summaryLine('output', destination),
  ];
  process.stdout.write(`${lines.join('\n')}\n`);
  return 0;
}

async function runStatements(argv) {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      options: {
        in: { type: 'string' },
        out: { type: 'string' },
        prior: { type: 'string' },
        currency: { type: 'string', default: 'EUR' },
        'prior-currency': { type: 'string' },
      },
      strict: true,
    });
  } catch (error) {
    return fail(`error: ${error.message}`);
  }

  const { in: input, out, prior, currency } = parsed.values;
  const priorCurrency = parsed.values['prior-currency'];
  if (!input) return fail('error: --in is required');
  if (!out) return fail('error: --out is required');
  try {
    parseCurrency(currency);
    if (priorCurrency) parseCurrency(priorCurrency);
  } catch (error) {
    return fail(`error: ${error.message}`);
  }

  let current;
  let result;
  try {
    current = await loadTrialBalance(input, null, currency);
    let priorBalance = null;
    if (prior) {
      priorBalance = await loadTrialBalance(prior, null, priorCurrency ?? currency);
      if ((priorCurrency ?? currency) !== currency) {
        priorBalance = statementsModule.restateTrialBalance(priorBalance, currency);
      }
    }
    result = statementsModule.build(current, priorBalance, currency);
  } catch (error) {
    if (
      error instanceof MissingColumn ||
      error instanceof CoaError ||
      error instanceof statementsModule.Unbalanced
    ) {
      process.stderr.write(`error: ${error.message}\n`);
      return 1;
    }
    throw error;
  }

  const destination = join(out, `${basename(input, extname(input))}-statements.xlsx`);
  await write(destination, statementsModule.toSheets(result));

  const lines = [
    `statements: ${basename(input)}`,
    summaryLine('accounts', current.lines.length),
    summaryLine('result', result.result),
    summaryLine('assets', result.assets),
    summaryLine('comparatives', result.hasPrior ? 'yes' : 'no'),
    summaryLine('unmapped', result.unmapped.length),
    summaryLine('output', destination),
  ];
  process.stdout.write(`${lines.join('\n')}\n`);
  return 0;
}

async function runReconcile(argv) {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      options: {
        bank: { type: 'string' },
        ledger: { type: 'string' },
        out: { type: 'string' },
        window: { type: 'string', default: String(reconcileModule.DEFAULT_WINDOW) },
        currency: { type: 'string', default: 'EUR' },
      },
      strict: true,
    });
  } catch (error) {
    return fail(`error: ${error.message}`);
  }

  const { bank, ledger: ledgerPath, out, window, currency } = parsed.values;
  if (!bank) return fail('error: --bank is required');
  if (!ledgerPath) return fail('error: --ledger is required');
  if (!out) return fail('error: --out is required');
  try {
    parseCurrency(currency);
  } catch (error) {
    return fail(`error: ${error.message}`);
  }
  const windowDays = Number(window);
  if (!Number.isInteger(windowDays)) return fail('error: --window must be a whole number');

  let result;
  try {
    const statement = await load(bank, null, STATEMENT_FIELDS);
    const ledger = await load(ledgerPath);
    result = reconcileModule.reconcile(statement, ledger, windowDays, currency);
  } catch (error) {
    if (error instanceof MissingColumn) {
      process.stderr.write(`error: ${error.message}\n`);
      return 1;
    }
    throw error;
  }

  const destination = join(out, `${basename(bank, extname(bank))}-reconciliation.xlsx`);
  await write(destination, reconcileModule.toSheets(result));

  const lines = [
    `reconcile: ${basename(bank)} against ${basename(ledgerPath)}`,
    summaryLine('confirmed', result.confirmed.length),
    summaryLine('proposed', result.proposed.length),
    summaryLine('bank unmatched', result.unmatchedStatement.length),
    summaryLine('ledger unmatched', result.unmatchedLedger.length),
    summaryLine('output', destination),
  ];
  process.stdout.write(`${lines.join('\n')}\n`);
  return 0;
}

export async function main(argv = process.argv.slice(2)) {
  const [command, ...rest] = argv;
  if (!command || command === '--help' || command === '-h') {
    process.stdout.write(USAGE);
    return command ? 0 : 2;
  }
  if (command === 'cleanup') return runCleanup(rest);
  if (command === 'generate') return runGenerate(rest);
  if (command === 'vat-return') return runVatReturn(rest);
  if (command === 'statements') return runStatements(rest);
  if (command === 'reconcile') return runReconcile(rest);
  return fail(`error: unknown command '${command}'\n\n${USAGE}`);
}

// Only run when executed directly, so tests can import main().
if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  process.exitCode = await main();
}
