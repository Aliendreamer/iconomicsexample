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

/** What shape of file to produce. Each of the five workflows needs one of these. */
export const KINDS = ['ledger', 'journal', 'trial-balance', 'bank'];

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
export class BadKind extends Error {}

// Shared value formulas. Extracted so a generated bank statement derives from the
// same numbers as the ledger for the same arguments — otherwise reconciling them
// would be meaningless.
const netCentsAt = (index) => 7500 + ((index * 21375) % 420000);
const vatCentsOf = (netCents, rate) => Math.floor((netCents * rate + 50) / 100);
const dayOf = (index, monthDays) => (index % monthDays) + 1;
const vendorAt = (index) => VENDORS[index % VENDORS.length];

/**
 * Counterparties used for the 0% rows in a journal, so an intra-EU supply and an
 * intra-EU acquisition both appear and the VIES list is non-empty.
 */
export const EU_COUNTERPARTIES = [
  ['Nordwind GmbH', 'DE811234567'],
  ['Zeta GmbH', 'DE811234567'],
];

/**
 * Accounts for a generated trial balance. Every code exists in config/coa.yaml,
 * so a generated file produces no unmapped accounts.
 */
export const TRIAL_ACCOUNTS = [
  ['204', 'Машини и оборудване', 'debit'],
  ['302', 'Материали', 'debit'],
  ['411', 'Клиенти', 'debit'],
  ['501', 'Каса', 'debit'],
  ['503', 'Разплащателна сметка', 'debit'],
  ['4531', 'ДДС покупки', 'debit'],
  ['601', 'Разходи за материали', 'debit'],
  ['602', 'Разходи за външни услуги', 'debit'],
  ['604', 'Разходи за заплати', 'debit'],
  ['603', 'Разходи за амортизации', 'debit'],
  ['241', 'Амортизация', 'credit'],
  ['101', 'Основен капитал', 'credit'],
  ['401', 'Доставчици', 'credit'],
  ['421', 'Персонал', 'credit'],
  ['4532', 'ДДС продажби', 'credit'],
  ['452', 'Данък върху печалбата', 'credit'],
  ['701', 'Приходи от продажби', 'credit'],
  ['703', 'Приходи от услуги', 'credit'],
];

/**
 * The plug account. Retained earnings is where a real trial balance absorbs the
 * difference, so it is the honest place to put it.
 */
export const PLUG_ACCOUNT = ['122', 'Неразпределена печалба'];

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

    const [vendor, vatNumber, account] = vendorAt(index);
    const description = DESCRIPTIONS[index % DESCRIPTIONS.length];
    const rate = RATES[index % RATES.length];
    const day = dayOf(index, monthDays);

    // Integer cents throughout: 7500 plus a fixed stride, wrapped. No floats.
    let netCents = netCentsAt(index);
    let vatCents = vatCentsOf(netCents, rate);

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

/**
 * A sales-and-purchases journal for the VAT return. Adds a direction column and
 * puts an EU counterparty on every 0% row, so VIES is non-empty.
 */
export function buildJournal(spec) {
  const columns = [
    'Дата',
    'Вид документ',
    'Контрагент',
    'ДДС номер',
    'Описание',
    'Сметка',
    'Данъчна основа',
    'ДДС',
    'Ставка',
    'Валута',
  ];
  const monthDays = daysInMonth(spec.year, spec.month);
  const rows = [];

  for (let index = 0; index < spec.rows; index += 1) {
    let [vendor, vatNumber, account] = vendorAt(index);
    const rate = RATES[index % RATES.length];
    // Deliberately period-5, not alternating: RATES has its 0% entry at position
    // 7, so a period-2 split would put every 0% row on the same side and one of
    // intra-EU supply / acquisition would never occur — leaving VIES permanently
    // empty. Periods 5 and 8 are coprime, so both appear.
    const isSale = index % 5 < 3;

    // A 0% row only makes sense with a non-domestic counterparty; a 0% row to a
    // BG counterparty is the ambiguous zero-rated/exempt case the classifier
    // deliberately refuses to decide, so keep it out of generated data.
    if (rate === 0) {
      [vendor, vatNumber] = EU_COUNTERPARTIES[index % EU_COUNTERPARTIES.length];
      account = isSale ? '701' : '302';
    }

    const netCents = netCentsAt(index);
    const vatCents = vatCentsOf(netCents, rate);
    rows.push([
      formatDate(spec.year, spec.month, dayOf(index, monthDays), spec.complexity, index),
      isSale ? 'Продажба' : 'Покупка',
      vendorSpelling(vendor, spec.complexity, index),
      vatNumber,
      DESCRIPTIONS[index % DESCRIPTIONS.length],
      account,
      formatAmount(netCents, spec.complexity),
      formatAmount(vatCents, spec.complexity),
      String(rate),
      'EUR',
    ]);
  }

  return { columns, rows };
}

/**
 * A trial balance that balances, because `statements` refuses one that does not.
 * The difference is absorbed by retained earnings, which is where a real trial
 * balance puts it. `rows` is capped at the account pool plus the plug: repeating
 * an account code in a trial balance would not be a real trial balance.
 */
export function buildTrialBalance(spec) {
  const usable = Math.min(Math.max(spec.rows - 1, 1), TRIAL_ACCOUNTS.length);
  const rows = [];
  let debitTotal = 0;
  let creditTotal = 0;

  for (let index = 0; index < usable; index += 1) {
    const [code, name, side] = TRIAL_ACCOUNTS[index];
    const cents = 50000 + ((index * 137500) % 4000000);
    if (side === 'debit') {
      debitTotal += cents;
      rows.push([code, name, formatAmount(cents, spec.complexity), formatAmount(0, spec.complexity)]);
    } else {
      creditTotal += cents;
      rows.push([code, name, formatAmount(0, spec.complexity), formatAmount(cents, spec.complexity)]);
    }
  }

  const difference = debitTotal - creditTotal;
  const [plugCode, plugName] = PLUG_ACCOUNT;
  if (difference >= 0) {
    rows.push([plugCode, plugName, formatAmount(0, spec.complexity), formatAmount(difference, spec.complexity)]);
  } else {
    // A debit balance on retained earnings is an accumulated loss. Valid.
    rows.push([plugCode, plugName, formatAmount(-difference, spec.complexity), formatAmount(0, spec.complexity)]);
  }

  return { columns: ['Сметка', 'Описание', 'Дебит', 'Кредит'], rows };
}

/**
 * A bank statement corresponding to the ledger for the same arguments.
 *
 * This only has value if it matches — a random statement reconciles against
 * nothing. So it derives from the same formulas as the ledger and then applies
 * the distortions a real bank export has: lagged value dates, uppercased
 * narration, roughly one payment in seven not yet cleared, and one bank charge
 * the ledger never recorded.
 */
export function buildBank(spec) {
  const monthDays = daysInMonth(spec.year, spec.month);
  const rows = [];

  for (let index = 0; index < spec.rows; index += 1) {
    // Mirror the ledger's own skips and unreadable rows.
    if (spec.complexity === 'nasty' && index % 29 === 13) continue;
    if (spec.complexity === 'nasty' && (index % 11 === 5 || index % 17 === 9)) continue;
    // Roughly one in seven payments has not cleared the bank.
    if (index % 7 === 3) continue;

    const [vendor] = vendorAt(index);
    let netCents = netCentsAt(index);
    if (spec.complexity === 'nasty' && index % 23 === 3) netCents = -netCents;
    const currency = spec.complexity !== 'clean' && index % 7 === 5 ? 'BGN' : 'EUR';

    // Value dates lag sometimes, not usually. Lagging most rows would push
    // nearly everything to `probable` and bury the tier distinction that is the
    // point of the reconciliation.
    const lag = index % 4 === 1 ? (index % 3) + 1 : 0;
    const day = Math.min(dayOf(index, monthDays) + lag, monthDays);

    const narration = `${vendor} ${DESCRIPTIONS[index % DESCRIPTIONS.length]}`.toUpperCase();
    rows.push([
      formatDate(spec.year, spec.month, day, spec.complexity, index),
      narration,
      formatAmount(netCents, spec.complexity),
      currency,
    ]);
  }

  // A charge the books never saw. The row a reconciliation exists to find.
  rows.push([
    formatDate(spec.year, spec.month, monthDays, spec.complexity, 0),
    'БАНКОВА ТАКСА ОБСЛУЖВАНЕ',
    formatAmount(1250, spec.complexity),
    'EUR',
  ]);

  return { columns: ['Дата', 'Основание', 'Сума', 'Валута'], rows };
}

/** Dispatch on the requested kind. */
export function buildFor(spec) {
  if (!KINDS.includes(spec.kind ?? 'ledger')) {
    throw new BadKind(`unknown kind '${spec.kind}'; expected one of ${KINDS.join(', ')}`);
  }
  const kind = spec.kind ?? 'ledger';
  if (kind === 'ledger') return build(spec);
  if (kind === 'journal') return buildJournal(spec);
  if (kind === 'trial-balance') return buildTrialBalance(spec);
  return buildBank(spec);
}

/** Summary lines for the CLI, so the user knows what they just got. */
export function describe(spec, sheet) {
  return [
    `kind: ${spec.kind ?? 'ledger'}`,
    `rows: ${sheet.rows.length}`,
    `complexity: ${spec.complexity}`,
    `period: ${String(spec.year).padStart(4, '0')}-${String(spec.month).padStart(2, '0')}`,
    `columns: ${sheet.columns.length}`,
  ];
}
