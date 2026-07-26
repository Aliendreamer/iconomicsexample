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
import { MissingColumn, load, write } from '../src/workbook.js';

export const SUMMARY_KEYS = ['rows in', 'rows clean', 'changes', 'exceptions', 'output'];
const LABEL_WIDTH = Math.max(...SUMMARY_KEYS.map((key) => key.length)) + 2;

function summaryLine(key, value) {
  return `  ${`${key}:`.padEnd(LABEL_WIDTH)} ${value}`;
}

const USAGE = `usage: iconomics cleanup --in <file.xlsx> --out <dir> [--currency EUR|BGN]

Bulgarian accounting toolkit

commands:
  cleanup   normalize a messy ledger export
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

export async function main(argv = process.argv.slice(2)) {
  const [command, ...rest] = argv;
  if (!command || command === '--help' || command === '-h') {
    process.stdout.write(USAGE);
    return command ? 0 : 2;
  }
  if (command === 'cleanup') return runCleanup(rest);
  return fail(`error: unknown command '${command}'\n\n${USAGE}`);
}

// Only run when executed directly, so tests can import main().
if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  process.exitCode = await main();
}
