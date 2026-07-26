/**
 * Chart of accounts: account code -> statement line.
 * Mirrors py/src/iconomics/coa.py.
 *
 * Treated as data, not code. The shipped codes are illustrative and meant to be
 * replaced with the firm's actual сметкоплан — see the warning in config/coa.yaml.
 */

import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import yaml from 'js-yaml';

import { ConfigError, findConfigDir } from './config.js';

export const PROFIT_AND_LOSS = 'profit_and_loss';
export const BALANCE_SHEET = 'balance_sheet';

export class CoaError extends ConfigError {}

export function loadCoa(configDir = null) {
  const directory = configDir ?? findConfigDir();
  const path = join(directory, 'coa.yaml');
  if (!existsSync(path)) throw new CoaError(`missing config file: ${path}`);

  const raw = yaml.load(readFileSync(path, 'utf-8')) ?? {};
  const entries = raw.accounts ?? {};
  if (Object.keys(entries).length === 0) throw new CoaError(`${path} defines no accounts`);

  const accounts = {};
  for (const [code, spec] of Object.entries(entries)) {
    const statement = String(spec.statement ?? '').trim();
    if (statement !== PROFIT_AND_LOSS && statement !== BALANCE_SHEET) {
      throw new CoaError(
        `${path}: account ${code} has statement '${statement}'; ` +
          `expected ${PROFIT_AND_LOSS} or ${BALANCE_SHEET}`,
      );
    }
    const side = String(spec.side ?? '').trim();
    if (side !== 'debit' && side !== 'credit') {
      throw new CoaError(
        `${path}: account ${code} has side '${side}'; expected debit or credit`,
      );
    }
    const key = String(code).trim();
    accounts[key] = {
      code: key,
      name: String(spec.name ?? '').trim(),
      statement,
      line: String(spec.line ?? '').trim(),
      side,
      cash: Boolean(spec.cash),
    };
  }

  const order = raw.line_order ?? {};
  const lineOrder = {
    [PROFIT_AND_LOSS]: (order[PROFIT_AND_LOSS] ?? []).map(String),
    [BALANCE_SHEET]: (order[BALANCE_SHEET] ?? []).map(String),
  };

  return {
    accounts,
    lineOrder,

    /**
     * Resolve a code, falling back to its parent for sub-accounts, so a firm
     * booking to 6021 still rolls up under 602.
     */
    get(code) {
      let key = String(code ?? '').trim();
      while (key) {
        if (key in accounts) return accounts[key];
        key = key.slice(0, -1);
      }
      return null;
    },

    orderedLines(statement) {
      return [...(lineOrder[statement] ?? [])];
    },

    cashAccounts() {
      return Object.keys(accounts)
        .filter((code) => accounts[code].cash)
        .sort();
    },
  };
}

/**
 * The normal side of the accounts mapped to this statement line.
 *
 * Resolved from the lexicographically smallest account code, not iteration
 * order: JavaScript objects reorder integer-like keys numerically while Python
 * dicts keep YAML order, so order-dependent logic would diverge.
 */
export function lineSide(lineName, coa) {
  for (const code of Object.keys(coa.accounts).sort()) {
    if (coa.accounts[code].line === lineName) return coa.accounts[code].side;
  }
  return 'debit';
}
