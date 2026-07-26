/**
 * The only module that touches .xlsx files. Mirrors py/src/iconomics/workbook.py.
 *
 * exceljs is promise-based, so load() and write() are async. That is the one
 * intentional shape difference from the Python API.
 *
 * Field names are camelCase per JavaScript convention (sourceRow, amountNet).
 * The spreadsheet column headers are what the parity test compares, and those
 * are identical between the two implementations.
 */

import { dirname } from 'node:path';
import { mkdirSync } from 'node:fs';
import ExcelJS from 'exceljs';
import Decimal from 'decimal.js';

import { loadHeaderAliases } from './config.js';
import { Money, defaultCurrencyFor } from './money.js';
import {
  UnparseableAmount,
  UnparseableDate,
  normalizeDirection,
  normalizeHeader,
  parseAmount,
  parseDate,
} from './parsing.js';

export const REQUIRED_FIELDS = ['date', 'counterparty', 'amount_net'];
/** A bank statement has no counterparty column — only a description. */
export const STATEMENT_FIELDS = ['date', 'amount_net'];

export class MissingColumn extends Error {}

/** exceljs returns rich objects for some cells; reduce them to primitives. */
function plain(value) {
  if (value === null || value === undefined) return null;
  if (value instanceof Date) return value;
  if (typeof value === 'object') {
    if ('result' in value) return value.result; // formula cell
    if ('richText' in value) return value.richText.map((part) => part.text).join('');
    if ('text' in value) return value.text; // hyperlink
  }
  return value;
}

const isBlank = (value) =>
  value === null || value === undefined || String(value).trim() === '';

/**
 * Render a rejected cell value for the Exceptions sheet. A blank cell says so
 * in words: "null" is a programmer's answer to an accountant's question.
 */
const describeRaw = (value) => (isBlank(value) ? '(blank)' : String(value));

function mapColumns(headerCells, aliases) {
  const mapping = {};
  const unmapped = [];
  headerCells.forEach((raw, index) => {
    if (isBlank(raw)) return;
    const canonical = aliases[normalizeHeader(raw)];
    if (canonical === undefined) unmapped.push(String(raw));
    else if (!(canonical in mapping)) mapping[canonical] = index;
  });
  return { mapping, unmapped };
}

const cellOf = (values, mapping, name) =>
  name in mapping && mapping[name] < values.length ? values[mapping[name]] : null;

export async function load(path, aliases = null, required = REQUIRED_FIELDS) {
  const resolved = aliases ?? loadHeaderAliases();
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.readFile(path);
  const sheet = workbook.worksheets[0];
  if (!sheet || sheet.rowCount === 0) throw new MissingColumn(`${path} is empty`);

  const width = sheet.columnCount;
  const allRows = [];
  sheet.eachRow({ includeEmpty: true }, (row) => {
    const values = [];
    for (let i = 1; i <= width; i += 1) values.push(plain(row.getCell(i).value));
    allRows.push(values);
  });

  const headers = allRows[0];
  const { mapping, unmapped } = mapColumns(headers, resolved);
  for (const requiredField of required) {
    if (!(requiredField in mapping)) {
      throw new MissingColumn(
        `${path} has no column mapping to '${requiredField}'; add an alias in config/headers.yaml`,
      );
    }
  }

  const rows = [];
  const problems = [];

  for (let index = 1; index < allRows.length; index += 1) {
    const values = allRows[index];
    const sourceRow = index + 1;
    if (values.every(isBlank)) continue;

    const rawDate = cellOf(values, mapping, 'date');
    let rowDate;
    try {
      rowDate = parseDate(rawDate);
    } catch (error) {
      if (!(error instanceof UnparseableDate)) throw error;
      problems.push({
        sourceRow,
        field: 'date',
        raw: describeRaw(rawDate),
        reason: error.message,
      });
      continue;
    }

    const rawNet = cellOf(values, mapping, 'amount_net');
    let net;
    try {
      net = parseAmount(rawNet);
    } catch (error) {
      if (!(error instanceof UnparseableAmount)) throw error;
      problems.push({
        sourceRow,
        field: 'amount_net',
        raw: describeRaw(rawNet),
        reason: error.message,
      });
      continue;
    }

    const currencyRaw = cellOf(values, mapping, 'currency');
    const currency = isBlank(currencyRaw)
      ? defaultCurrencyFor(rowDate)
      : String(currencyRaw).trim().toUpperCase();

    const vatRaw = cellOf(values, mapping, 'vat_amount');
    let vatAmount = null;
    if (!isBlank(vatRaw)) {
      try {
        vatAmount = new Money(parseAmount(vatRaw), currency);
      } catch (error) {
        if (!(error instanceof UnparseableAmount)) throw error;
        problems.push({
          sourceRow,
          field: 'vat_amount',
          raw: describeRaw(vatRaw),
          reason: error.message,
        });
        continue;
      }
    }

    const rateRaw = cellOf(values, mapping, 'vat_rate');
    let vatRate = null;
    if (!isBlank(rateRaw)) {
      try {
        vatRate = parseAmount(rateRaw);
      } catch (error) {
        if (!(error instanceof UnparseableAmount)) throw error;
        problems.push({
          sourceRow,
          field: 'vat_rate',
          raw: describeRaw(rateRaw),
          reason: error.message,
        });
        continue;
      }
    }

    const extra = {};
    headers.forEach((header, columnIndex) => {
      if (!isBlank(header) && unmapped.includes(String(header))) {
        extra[String(header)] = values[columnIndex] ?? null;
      }
    });

    const numberRaw = cellOf(values, mapping, 'vat_number');
    const accountRaw = cellOf(values, mapping, 'account');
    const descriptionRaw = cellOf(values, mapping, 'description');
    const counterpartyRaw = cellOf(values, mapping, 'counterparty');

    rows.push({
      sourceRow,
      date: rowDate,
      counterparty: String(counterpartyRaw ?? '').trim(),
      description: String(descriptionRaw ?? '').trim(),
      amountNet: new Money(net, currency),
      currency,
      vatNumber: isBlank(numberRaw) ? null : String(numberRaw).trim(),
      vatAmount,
      vatRate,
      account: isBlank(accountRaw) ? null : String(accountRaw).trim(),
      direction: normalizeDirection(cellOf(values, mapping, 'direction')),
      extra,
    });
  }

  return { rows, problems, unmappedHeaders: unmapped, sourcePath: String(path) };
}

/**
 * Flatten a value into something exceljs can store.
 *
 * This is the one place a float is permitted: the value is leaving the system
 * into a spreadsheet cell, after all arithmetic is complete, and is never read
 * back for computation.
 */
function serialize(value) {
  if (value instanceof Money) return value.amount.toNumber();
  if (Decimal.isDecimal(value)) return value.toNumber();
  // An empty string and a blank cell must not be different things: openpyxl
  // reads "" back as None while exceljs reads it back as "", which would make
  // the two implementations disagree on cells that are both simply empty.
  if (value === '') return null;
  return value ?? null;
}

export async function write(path, sheets) {
  const workbook = new ExcelJS.Workbook();

  for (const [name, spec] of Object.entries(sheets)) {
    const sheet = workbook.addWorksheet(name);
    sheet.addRow(spec.columns);
    const header = sheet.getRow(1);
    header.font = { bold: true };
    header.eachCell((cell) => {
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFDDDDDD' } };
      cell.alignment = { vertical: 'middle' };
    });
    spec.rows.forEach((row) => sheet.addRow(row.map(serialize)));

    const formats = spec.numberFormats ?? {};
    for (const [columnName, numberFormat] of Object.entries(formats)) {
      const columnIndex = spec.columns.indexOf(columnName);
      if (columnIndex === -1) continue;
      for (let rowIndex = 2; rowIndex < spec.rows.length + 2; rowIndex += 1) {
        sheet.getRow(rowIndex).getCell(columnIndex + 1).numFmt = numberFormat;
      }
    }

    sheet.views = [{ state: 'frozen', ySplit: 1 }];
    spec.columns.forEach((column, index) => {
      const widths = spec.rows.map((row) => String(serialize(row[index]) ?? '').length);
      sheet.getColumn(index + 1).width = Math.min(
        Math.max(column.length, ...widths, 0) + 2,
        48,
      );
    });
  }

  mkdirSync(dirname(path), { recursive: true });
  await workbook.xlsx.writeFile(path);
}
