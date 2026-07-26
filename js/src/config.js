/**
 * Loads the YAML rule files. Mirrors py/src/iconomics/config.py.
 *
 * js-yaml v4's `load` uses the default safe schema — it cannot construct
 * arbitrary types, and is the direct equivalent of Python's `yaml.safe_load`.
 * (v3's `safeLoad` was removed precisely because `load` became safe.) Do not
 * pass a custom schema here.
 */

import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import yaml from 'js-yaml';

import { normalizeHeader } from './parsing.js';

export const CANONICAL_FIELDS = [
  'date',
  'counterparty',
  'vat_number',
  'description',
  'amount_net',
  'vat_amount',
  'vat_rate',
  'account',
  'currency',
];

export class ConfigError extends Error {}

export function findConfigDir() {
  let current = dirname(fileURLToPath(import.meta.url));
  for (;;) {
    const candidate = join(current, 'config');
    if (existsSync(join(candidate, 'headers.yaml'))) return candidate;
    const parent = resolve(current, '..');
    if (parent === current) break;
    current = parent;
  }
  throw new ConfigError('could not locate config/headers.yaml above this module');
}

export function loadHeaderAliases(configDir = null) {
  const directory = configDir ?? findConfigDir();
  const path = join(directory, 'headers.yaml');
  if (!existsSync(path)) throw new ConfigError(`missing config file: ${path}`);

  const raw = yaml.load(readFileSync(path, 'utf-8')) ?? {};
  const aliases = {};
  for (const [field, values] of Object.entries(raw)) {
    if (!CANONICAL_FIELDS.includes(field)) {
      throw new ConfigError(
        `unknown canonical field '${field}' in ${path}; ` +
          `expected one of ${CANONICAL_FIELDS.join(', ')}`,
      );
    }
    for (const value of values ?? []) {
      aliases[normalizeHeader(value)] = field;
    }
  }
  return aliases;
}
