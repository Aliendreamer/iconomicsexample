/**
 * Bulgarian VAT return: sales journal, purchase journal, declaration, VIES.
 * Mirrors py/src/iconomics/vat.py.
 *
 * The declaration totals are derived from the journal rows rather than computed
 * alongside them: two independent computations can disagree, and a return whose
 * declaration does not tie to its journals is rejected.
 *
 * Classification is data-driven — from the rate column and the counterparty's VAT
 * number prefix — never guessed from description text.
 */

import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import Decimal from 'decimal.js';
import yaml from 'js-yaml';

import { ConfigError, findConfigDir } from './config.js';
import { Money } from './money.js';
import { isoDay } from './parsing.js';

export const SALES_COLUMNS = [
  'Source Row',
  'Date',
  'Counterparty',
  'VAT Number',
  'Description',
  'Treatment',
  'Rate %',
  'Taxable Base',
  'VAT',
];
export const PURCHASE_COLUMNS = [...SALES_COLUMNS];
export const DECLARATION_COLUMNS = ['Line', 'Description', 'Amount'];
export const VIES_COLUMNS = ['Source Row', 'Date', 'Counterparty', 'VAT Number', 'Amount'];
export const RECONCILIATION_COLUMNS = [
  'Check',
  'From Journals',
  'From Declaration',
  'Agrees',
];

export const MONEY_FORMATS = { 'Taxable Base': '0.00', VAT: '0.00', Amount: '0.00' };

export const STANDARD = 'standard';
export const REDUCED = 'reduced';
export const INTRA_EU_SUPPLY = 'intra_eu_supply';
export const INTRA_EU_ACQUISITION = 'intra_eu_acquisition';
export const ZERO_DOMESTIC = 'zero_domestic';

export const TREATMENT_LABELS = {
  [STANDARD]: 'Облагаема доставка 20%',
  [REDUCED]: 'Облагаема доставка 9%',
  [INTRA_EU_SUPPLY]: 'Вътреобщностна доставка (0%)',
  [INTRA_EU_ACQUISITION]: 'Вътреобщностно придобиване (обратно начисляване)',
  [ZERO_DOMESTIC]: 'Нулева ставка / освободена — за проверка',
};

export class VatConfigError extends ConfigError {}

export function loadVatConfig(configDir = null) {
  const directory = configDir ?? findConfigDir();
  const path = join(directory, 'vat-rates.yaml');
  if (!existsSync(path)) throw new VatConfigError(`missing config file: ${path}`);

  const raw = yaml.load(readFileSync(path, 'utf-8')) ?? {};
  const rates = raw.rates ?? {};
  for (const key of ['standard', 'reduced', 'zero']) {
    if (!(key in rates)) throw new VatConfigError(`${path}: rates.${key} is required`);
  }

  return {
    standard: new Decimal(String(rates.standard)),
    reduced: new Decimal(String(rates.reduced)),
    zero: new Decimal(String(rates.zero)),
    filingDay: Number(raw.filing_day ?? 14),
    domesticPrefix: String(raw.domestic_prefix ?? 'BG').toUpperCase(),
    declarationCells: { ...(raw.declaration_cells ?? {}) },
    get knownRates() {
      return [this.standard, this.reduced, this.zero];
    },
  };
}

/**
 * Fall back to the account code when the ledger has no direction column.
 * A 7xx account is revenue, so a sale. This is an inference, and rows reaching
 * it are surfaced in the run summary rather than silently trusted.
 */
export function inferDirection(row) {
  if (row.direction !== null && row.direction !== undefined) return row.direction;
  const account = (row.account ?? '').trim();
  if (account.startsWith('7')) return 'sale';
  if (account) return 'purchase';
  return null;
}

function isDomestic(vatNumber, config) {
  if (!vatNumber) return true; // no VAT number at all: domestic, not intra-EU
  return vatNumber.trim().toUpperCase().startsWith(config.domesticPrefix);
}

/** Return a treatment code, or null if the rules do not cover this row. */
export function classify(row, direction, config) {
  if (row.vatRate === null || row.vatRate === undefined) return null;
  const rate = row.vatRate;

  if (rate.equals(config.standard)) return STANDARD;
  if (rate.equals(config.reduced)) return REDUCED;
  if (rate.equals(config.zero)) {
    if (isDomestic(row.vatNumber, config)) {
      // Zero-rated and exempt are different things with different consequences,
      // and the rate alone does not distinguish them.
      return ZERO_DOMESTIC;
    }
    return direction === 'sale' ? INTRA_EU_SUPPLY : INTRA_EU_ACQUISITION;
  }
  return null;
}

function sumMoney(values, currency) {
  let total = new Money(new Decimal('0.00'), currency);
  for (const value of values) total = total.add(value);
  return total;
}

export function buildReturn(ledger, currency = 'EUR') {
  const config = loadVatConfig();

  const sales = [];
  const purchases = [];
  const vies = [];
  const unclassified = [];

  for (const row of ledger.rows) {
    const direction = inferDirection(row);
    if (direction === null) {
      unclassified.push({
        sourceRow: row.sourceRow,
        field: 'direction',
        raw: row.description || '(no description)',
        reason:
          'cannot tell whether this is a sale or a purchase; add a direction ' +
          'column or an account code',
      });
      continue;
    }

    const treatment = classify(row, direction, config);
    if (treatment === null) {
      unclassified.push({
        sourceRow: row.sourceRow,
        field: 'vat_rate',
        raw:
          row.vatRate === null || row.vatRate === undefined
            ? '(blank)'
            : row.vatRate.toString(),
        reason:
          'no VAT treatment matches this rate; expected one of ' +
          config.knownRates.map((r) => r.toString()).join(', '),
      });
      continue;
    }

    const entry = { row, direction, treatment, rate: row.vatRate };
    (direction === 'sale' ? sales : purchases).push(entry);
    if (treatment === INTRA_EU_SUPPLY) vies.push(entry);
  }

  const bases = (entries, treatment) =>
    entries.filter((e) => e.treatment === treatment).map((e) => e.row.amountNet);
  const taxes = (entries, treatment) =>
    entries
      .filter((e) => e.treatment === treatment && e.row.vatAmount !== null)
      .map((e) => e.row.vatAmount);

  const totals = {
    base_standard: sumMoney(bases(sales, STANDARD), currency),
    vat_standard: sumMoney(taxes(sales, STANDARD), currency),
    base_reduced: sumMoney(bases(sales, REDUCED), currency),
    vat_reduced: sumMoney(taxes(sales, REDUCED), currency),
    base_intra_eu_supply: sumMoney(bases(sales, INTRA_EU_SUPPLY), currency),
    base_zero_domestic: sumMoney(bases(sales, ZERO_DOMESTIC), currency),
    base_purchases: sumMoney(
      purchases.map((e) => e.row.amountNet),
      currency,
    ),
    vat_input: sumMoney(
      purchases.filter((e) => e.row.vatAmount !== null).map((e) => e.row.vatAmount),
      currency,
    ),
  };
  totals.vat_output = totals.vat_standard.add(totals.vat_reduced);
  totals.vat_net = totals.vat_output.sub(totals.vat_input);

  return { sales, purchases, vies, unclassified, currency, config, totals };
}

const byDateThenRow = (a, b) =>
  a.row.date - b.row.date || a.row.sourceRow - b.row.sourceRow;

function journalRows(entries) {
  return [...entries].sort(byDateThenRow).map((e) => [
    e.row.sourceRow,
    isoDay(e.row.date),
    e.row.counterparty,
    e.row.vatNumber ?? '',
    e.row.description,
    TREATMENT_LABELS[e.treatment],
    e.rate,
    e.row.amountNet,
    e.row.vatAmount ?? '',
  ]);
}

/** Declaration lines, in filing order. Keys match config declarationCells. */
export const DECLARATION_LINES = [
  ['base_standard', 'Данъчна основа на облагаеми доставки 20%'],
  ['vat_standard', 'Начислен ДДС 20%'],
  ['base_reduced', 'Данъчна основа на облагаеми доставки 9%'],
  ['vat_reduced', 'Начислен ДДС 9%'],
  ['base_intra_eu_supply', 'Данъчна основа на вътреобщностни доставки (0%)'],
  ['base_zero_domestic', 'Данъчна основа, нулева ставка / освободена'],
  ['vat_output', 'Общо начислен ДДС за периода'],
  ['base_purchases', 'Данъчна основа на получени доставки'],
  ['vat_input', 'ДДС с право на данъчен кредит'],
  ['vat_net', 'ДДС за внасяне (+) / за възстановяване (-)'],
];

export function toSheets(result) {
  const declarationRows = DECLARATION_LINES.map(([key, label]) => [
    result.config.declarationCells[key] ?? '',
    label,
    result.totals[key],
  ]);

  const journalOutput = sumMoney(
    result.sales.filter((e) => e.row.vatAmount !== null).map((e) => e.row.vatAmount),
    result.currency,
  );
  const journalInput = sumMoney(
    result.purchases.filter((e) => e.row.vatAmount !== null).map((e) => e.row.vatAmount),
    result.currency,
  );

  const reconciliationRows = [
    [
      'Начислен ДДС (sales journal vs declaration)',
      journalOutput,
      result.totals.vat_output,
      journalOutput.equals(result.totals.vat_output) ? 'yes' : 'NO',
    ],
    [
      'Данъчен кредит (purchase journal vs declaration)',
      journalInput,
      result.totals.vat_input,
      journalInput.equals(result.totals.vat_input) ? 'yes' : 'NO',
    ],
  ];

  const viesRows = [...result.vies]
    .sort(byDateThenRow)
    .map((e) => [
      e.row.sourceRow,
      isoDay(e.row.date),
      e.row.counterparty,
      e.row.vatNumber ?? '',
      e.row.amountNet,
    ]);

  return {
    'Дневник продажби': {
      columns: SALES_COLUMNS,
      rows: journalRows(result.sales),
      numberFormats: MONEY_FORMATS,
    },
    'Дневник покупки': {
      columns: PURCHASE_COLUMNS,
      rows: journalRows(result.purchases),
      numberFormats: MONEY_FORMATS,
    },
    Декларация: {
      columns: DECLARATION_COLUMNS,
      rows: declarationRows,
      numberFormats: MONEY_FORMATS,
    },
    VIES: { columns: VIES_COLUMNS, rows: viesRows, numberFormats: MONEY_FORMATS },
    Reconciliation: {
      columns: RECONCILIATION_COLUMNS,
      rows: reconciliationRows,
      numberFormats: { 'From Journals': '0.00', 'From Declaration': '0.00' },
    },
    Exceptions: {
      columns: ['Source Row', 'Field', 'Raw Value', 'Reason'],
      rows: result.unclassified.map((p) => [p.sourceRow, p.field, p.raw, p.reason]),
    },
  };
}
