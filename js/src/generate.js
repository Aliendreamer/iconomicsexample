/**
 * Generate sample ledger exports at a requested size and messiness.
 * Mirrors py/src/iconomics/generate.py exactly.
 *
 * Two constraints shape this module:
 *
 *   - Deterministic. No randomness anywhere. The same arguments produce a
 *     byte-identical file every time.
 *   - Identical across languages. Every wrinkle is injected at a fixed row
 *     index and all money is computed in integer cents. A shared PRNG or any
 *     float arithmetic would drift between Python and JavaScript.
 */

export const COMPLEXITIES = ['clean', 'messy', 'nasty'];

// Pools are cycled by row index. Order matters: it is part of the contract with
// the Python implementation.
export const VENDORS = [
  ['Алфа ООД', 'BG123456789', '602'],
  ['Бета ЕООД', 'BG987654321', '601'],
  ['Гама АД', 'BG555444333', '601'],
  ['Делта ООД', 'BG111222333', '602'],
  ['Епсилон ЕООД', 'BG444555666', '602'],
  ['Йота ЕООД', 'BG333222111', '602'],
  ['Хотел Родина АД', 'BG777888999', '606'],
  ['Zeta GmbH', 'DE811234567', '701'],
];

export const DESCRIPTIONS = [
  'Консултантски услуги',
  'Наем помещение',
  'Софтуерен абонамент',
  'Транспортни разходи',
  'Материали',
  'Поддръжка техника',
  'Нощувки командировка',
  'Интра-общностна доставка',
];

// VAT rate per row, cycled. 9% is accommodation, 0% is an intra-EU supply.
export const RATES = [20, 20, 20, 20, 20, 20, 9, 0];

const MONTHS_SHORT = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export class BadComplexity extends Error {}

/** Header row. Each level spells things slightly differently on purpose. */
function headersFor(complexity) {
  if (complexity === 'clean') {
    return [
      'Дата',
      'Контрагент',
      'ДДС номер',
      'Описание',
      'Сметка',
      'Сума без ДДС',
      'ДДС',
      'Ставка',
      'Валута',
    ];
  }
  if (complexity === 'messy') {
    return [
      'Дата',
      'Контрагент',
      'ДДС номер',
      'Описание',
      'Сметка',
      'Данъчна основа',
      'ДДС',
      'Ставка',
      'Валута',
    ];
  }
  // nasty: the alternate counterparty spelling, plus a column the toolkit does
  // not know and must carry through rather than drop.
  return [
    'Дата',
    'Партньор',
    'ДДС номер',
    'Описание',
    'Сметка',
    'Данъчна основа',
    'ДДС',
    'Ставка',
    'Валута',
    'Вътрешен код',
  ];
}

/** Insert spaces every three digits from the right: 1234567 -> '1 234 567'. */
function groupThousands(digits) {
  const parts = [];
  let rest = digits;
  while (rest.length > 3) {
    parts.unshift(rest.slice(-3));
    rest = rest.slice(0, -3);
  }
  parts.unshift(rest);
  return parts.join(' ');
}

/** Render an amount the way the chosen level of export would write it. */
function formatAmount(cents, complexity) {
  const negative = cents < 0;
  const magnitude = Math.abs(cents);
  const whole = Math.floor(magnitude / 100);
  const fraction = magnitude % 100;
  const fractionText = String(fraction).padStart(2, '0');

  if (complexity === 'clean') {
    const text = `${whole}.${fractionText}`;
    return negative ? `-${text}` : text;
  }

  const text = `${groupThousands(String(whole))},${fractionText}`;
  return negative ? `(${text})` : text;
}

/** Days since the 1899-12-30 epoch openpyxl and exceljs both use. */
function excelSerial(year, month, day) {
  const epoch = Date.UTC(1899, 11, 30);
  return Math.round((Date.UTC(year, month - 1, day) - epoch) / 86400000);
}

function formatDate(year, month, day, complexity, index) {
  if (complexity === 'clean') {
    return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  }
  if (index % 9 === 4) {
    // A date stored as a raw number, which is what Excel actually holds.
    return excelSerial(year, month, day);
  }
  if (complexity === 'nasty' && index % 13 === 6) {
    return `${day}-${MONTHS_SHORT[month - 1]}-${String(year % 100).padStart(2, '0')}`;
  }
  return `${String(day).padStart(2, '0')}.${String(month).padStart(2, '0')}.${String(year).padStart(4, '0')}`;
}

/**
 * Introduce the cosmetic variants that make vendor merging necessary.
 *
 * Note replaceAll, not replace: Python's str.replace substitutes every
 * occurrence, and JavaScript's String.replace with a string pattern
 * substitutes only the first. That difference would break parity.
 */
function vendorSpelling(name, complexity, index) {
  if (complexity === 'clean') return name;
  if (index % 5 === 2) return name.toUpperCase();
  if (index % 5 === 3) return `${name.replaceAll(' ', '  ')}.`;
  return name;
}

const daysInMonth = (year, month) => new Date(Date.UTC(year, month, 0)).getUTCDate();

/** Build the sheet for a generation request. */
export function build(spec) {
  if (!COMPLEXITIES.includes(spec.complexity)) {
    throw new BadComplexity(
      `unknown complexity '${spec.complexity}'; expected one of ${COMPLEXITIES.join(', ')}`,
    );
  }
  if (spec.rows < 1) throw new Error('rows must be at least 1');

  const columns = headersFor(spec.complexity);
  const monthDays = daysInMonth(spec.year, spec.month);
  const rows = [];

  for (let index = 0; index < spec.rows; index += 1) {
    // A duplicated transaction: identical in every field to the row above.
    if (spec.complexity === 'nasty' && index % 29 === 13 && rows.length > 0) {
      rows.push([...rows[rows.length - 1]]);
      continue;
    }

    const [vendor, vatNumber, account] = VENDORS[index % VENDORS.length];
    const description = DESCRIPTIONS[index % DESCRIPTIONS.length];
    const rate = RATES[index % RATES.length];
    const day = (index % monthDays) + 1;

    // Integer cents throughout: 7500 plus a fixed stride, wrapped. No floats.
    let netCents = 7500 + ((index * 21375) % 420000);
    let vatCents = Math.floor((netCents * rate + 50) / 100);

    // A credit note, written the way accountants write negatives.
    if (spec.complexity === 'nasty' && index % 23 === 3) {
      netCents = -netCents;
      vatCents = -vatCents;
    }

    // A tenth of rows in the messy levels are still booked in BGN — the
    // correction entries that keep appearing long after the changeover.
    const currency = spec.complexity !== 'clean' && index % 7 === 5 ? 'BGN' : 'EUR';

    let dateCell = formatDate(spec.year, spec.month, day, spec.complexity, index);
    let counterparty = vendorSpelling(vendor, spec.complexity, index);
    let netCell = formatAmount(netCents, spec.complexity);
    const vatCell = formatAmount(vatCents, spec.complexity);

    if (spec.complexity === 'nasty') {
      if (index % 11 === 5) netCell = '—'; // an em dash where a number belongs
      if (index % 17 === 9) dateCell = '';
      if (index % 19 === 7) counterparty = '';
    }

    const row = [
      dateCell,
      counterparty,
      vatNumber,
      description,
      account,
      netCell,
      vatCell,
      String(rate),
      currency,
    ];
    if (spec.complexity === 'nasty') {
      row.push(`INT-${String(index + 1).padStart(4, '0')}`);
    }

    rows.push(row);
  }

  return { columns, rows };
}

/** Summary lines for the CLI, so the user knows what they just got. */
export function describe(spec, sheet) {
  return [
    `rows: ${sheet.rows.length}`,
    `complexity: ${spec.complexity}`,
    `period: ${String(spec.year).padStart(4, '0')}-${String(spec.month).padStart(2, '0')}`,
    `columns: ${sheet.columns.length}`,
  ];
}
