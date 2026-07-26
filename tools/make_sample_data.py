#!/usr/bin/env python3
"""Generate the deliberately messy sample ledgers.

Everything here is hardcoded. No randomness and no reference to the current
date, because data/expected/ golden files are compared exactly and would
otherwise churn on every run.

Run from the repo root:  python tools/make_sample_data.py
"""

from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "raw"

# December 2025: pre-euro, everything in BGN, Bulgarian date and number formats.
DECEMBER = {
    "headers": ["Дата", "Контрагент", "ДДС номер", "Описание", "Сума без ДДС", "ДДС"],
    "rows": [
        ["01.12.2025", "Алфа ООД", "BG123456789", "Консултантски услуги", "1 200,00", "240,00"],
        ["05.12.2025", "Бета ЕООД", "BG987654321", "Наем офис", "800,50", "160,10"],
        ["17.12.2025", "Гама АД", "BG555444333", "Софтуерен абонамент", "349,99", "70,00"],
        ["31.12.2025", "Алфа ООД", "BG123456789", "Годишна такса", "2 500,00", "500,00"],
    ],
}

# January 2026: dual circulation month. Explicit currency column, mixed values.
JANUARY = {
    "headers": [
        "Дата",
        "Контрагент",
        "ДДС номер",
        "Описание",
        "Сума без ДДС",
        "ДДС",
        "Валута",
    ],
    "rows": [
        ["05.01.2026", "Алфа ООД", "BG123456789", "Консултантски услуги", "1 000,00", "200,00", "BGN"],
        [46027, "Бета ЕООД ", "BG987654321", "Наем офис", "410,00", "82,00", "EUR"],
        [46030, "Бета ЕООД", "BG987654321", "Наем склад", "205,00", "41,00", "EUR"],
        ["20.01.2026", "Делта ООД", "BG111222333", "Транспорт", "150,75", "30,15", "BGN"],
        ["28.01.2026", "Гама АД", "BG555444333", "Софтуерен абонамент", "179,00", "35,80", "EUR"],
    ],
}

# February 2026: euro only, different header spelling, planted bad rows.
FEBRUARY = {
    "headers": ["Дата", "Партньор", "ДДС номер", "Описание", "Сума без ДДС", "ДДС"],
    "rows": [
        ["1-Feb-26", "Алфа ООД", "BG123456789", "Консултантски услуги", "512.00", "102.40"],
        ["03.02.2026", "Алфа ООД.", "BG123456789", "Допълнителни услуги", "128.00", "25.60"],
        ["11.02.2026", "Епсилон ЕООД", "BG444555666", "Счетоводен софтуер", "1.234", "246.80"],
        ["14.02.2026", "Делта ООД", "BG111222333", "Транспорт", "n/a", "12.00"],
        ["", "Гама АД", "BG555444333", "Липсва дата", "99.00", "19.80"],
        ["28.02.2026", "Бета ЕООД", "BG987654321", "Наем офис", "410.00", "82.00"],
    ],
}


# March 2026: the hard one. Every wrinkle a real export throws at you at once.
#
#   * a fuller header set — account codes, VAT rate, an internal code column the
#     toolkit does not know and must preserve rather than drop
#   * three spellings of the same vendor, including a case variant
#   * a credit note written in accounting parentheses
#   * a late correction entry still recorded in BGN, months after the changeover
#   * the 9% reduced rate (accommodation) and a 0% intra-EU supply side by side
#   * a duplicate transaction, identical in every field
#   * a row with no counterparty at all
#   * an em dash where an amount should be
MARCH = {
    "headers": [
        "Дата",
        "Партньор",
        "ДДС номер",
        "Описание",
        "Сметка",
        "Данъчна основа",
        "ДДС",
        "Ставка",
        "Валута",
        "Вътрешен код",
    ],
    "rows": [
        ["1-Mar-26", "Алфа ООД", "BG123456789", "Консултантски услуги", "602", "1 500,00", "300,00", "20", "EUR", "INT-001"],
        ["02.03.2026", "АЛФА ООД", "BG123456789", "Допълнителни часове", "602", "375,00", "75,00", "20", "EUR", "INT-002"],
        ["03.03.2026", "Алфа  ООД.", "BG123456789", "Кредитно известие", "602", "(240,00)", "(48,00)", "20", "EUR", "INT-003"],
        ["2026-03-05", "Хотел Родина АД", "BG777888999", "Нощувки командировка", "606", "450,00", "40,50", "9", "EUR", "INT-004"],
        # 46085 is 2026-03-04 as an Excel serial (2026-01-01 is 46023).
        [46085, "Zeta GmbH", "DE811234567", "Интра-общностна доставка", "701", "2 800,00", "0,00", "0", "EUR", "INT-005"],
        ["09.03.2026", "Бета ЕООД", "BG987654321", "Наем офис март", "601", "410,00", "82,00", "20", "EUR", "INT-006"],
        ["10.03.2026", "Делта ООД", "BG111222333", "Корекция 2025 г.", "602", "150,75", "30,15", "20", "BGN", "INT-007"],
        ["12.03.2026", "Епсилон ЕООД", "BG444555666", "Счетоводен софтуер", "602", "1 234,00", "246,80", "20", "EUR", "INT-008"],
        ["16.03.2026", "Гама АД", "BG555444333", "Транспортни разходи", "601", "—", "12,00", "20", "EUR", "INT-009"],
        ["18.03.2026", "", "BG000111222", "Липсва контрагент", "601", "88,00", "17,60", "20", "EUR", "INT-010"],
        ["20.03.2026", "Бета ЕООД", "BG987654321", "Наем склад", "601", "205,00", "41,00", "20", "EUR", "INT-011"],
        ["20.03.2026", "Бета ЕООД", "BG987654321", "Наем склад", "601", "205,00", "41,00", "20", "EUR", "INT-011"],
        ["25.03.2026", "Йота ЕООД", "BG333222111", "Ремонт техника", "602", "1 049,99", "210,00", "20", "EUR", "INT-012"],
        ["31.03.2026", "Алфа ООД", "BG123456789", "Месечна такса", "602", "500,00", "100,00", "20", "EUR", "INT-013"],
    ],
}


def build_q1_large() -> dict:
    """A volume file: 48 rows across Q1 2026, built deterministically.

    The point is scale rather than novelty — enough rows that reading the
    output by hand stops being reasonable, which is when the toolkit starts
    earning its keep. No randomness: the pattern is a fixed cycle so the file
    is byte-identical on every run.
    """
    vendors = [
        ("Алфа ООД", "BG123456789", "602"),
        ("Бета ЕООД", "BG987654321", "601"),
        ("Гама АД", "BG555444333", "601"),
        ("Делта ООД", "BG111222333", "602"),
        ("Епсилон ЕООД", "BG444555666", "602"),
        ("Йота ЕООД", "BG333222111", "602"),
    ]
    descriptions = [
        "Консултантски услуги",
        "Наем помещение",
        "Софтуерен абонамент",
        "Транспорт",
        "Материали",
        "Поддръжка",
    ]
    rows = []
    for index in range(48):
        vendor, vat_number, account = vendors[index % len(vendors)]
        month = index % 3 + 1
        day = index % 27 + 1
        # A tenth of the rows are late BGN entries needing restatement.
        currency = "BGN" if index % 10 == 3 else "EUR"
        net = 100 + index * 37.5
        vat = round(net * 0.2, 2)
        rows.append(
            [
                f"{day:02d}.{month:02d}.2026",
                vendor,
                vat_number,
                descriptions[index % len(descriptions)],
                account,
                f"{net:.2f}".replace(".", ","),
                f"{vat:.2f}".replace(".", ","),
                "20",
                currency,
            ]
        )
    return {
        "headers": [
            "Дата",
            "Контрагент",
            "ДДС номер",
            "Описание",
            "Сметка",
            "Данъчна основа",
            "ДДС",
            "Ставка",
            "Валута",
        ],
        "rows": rows,
    }


# A sales-and-purchases journal for the VAT return. Has an explicit direction
# column, VAT rates covering 20% / 9% / 0%, and one EU counterparty each way so
# both an intra-EU supply and an intra-EU acquisition appear.
JOURNAL = {
    "headers": [
        "Дата",
        "Вид документ",
        "Контрагент",
        "ДДС номер",
        "Описание",
        "Сметка",
        "Данъчна основа",
        "ДДС",
        "Ставка",
        "Валута",
    ],
    "rows": [
        ["02.03.2026", "Продажба", "Клиент Омега ООД", "BG222333444", "Услуги март", "703", "5 000,00", "1 000,00", "20", "EUR"],
        ["05.03.2026", "Продажба", "Клиент Сигма АД", "BG666777888", "Стоки", "701", "2 500,00", "500,00", "20", "EUR"],
        ["09.03.2026", "Продажба", "Hotel Guest Ltd", "BG999888777", "Нощувки", "703", "1 200,00", "108,00", "9", "EUR"],
        ["12.03.2026", "Продажба", "Nordwind GmbH", "DE811234567", "ВОД стоки", "701", "3 400,00", "0,00", "0", "EUR"],
        ["18.03.2026", "Продажба", "Клиент Омега ООД", "BG222333444", "Допълнителни услуги", "703", "800,00", "160,00", "20", "EUR"],
        ["03.03.2026", "Покупка", "Алфа ООД", "BG123456789", "Консултантски услуги", "602", "1 500,00", "300,00", "20", "EUR"],
        ["07.03.2026", "Покупка", "Бета ЕООД", "BG987654321", "Наем офис", "601", "410,00", "82,00", "20", "EUR"],
        ["11.03.2026", "Покупка", "Хотел Родина АД", "BG777888999", "Нощувки командировка", "606", "450,00", "40,50", "9", "EUR"],
        ["14.03.2026", "Покупка", "Zeta GmbH", "DE811234567", "ВОП материали", "302", "2 800,00", "0,00", "0", "EUR"],
        ["20.03.2026", "Покупка", "Епсилон ЕООД", "BG444555666", "Софтуер", "602", "1 234,00", "246,80", "20", "EUR"],
        # A rate the rules do not cover — goes to the Exceptions sheet, not a guess.
        ["25.03.2026", "Покупка", "Йота ЕООД", "BG333222111", "Неясна ставка", "602", "500,00", "35,00", "7", "EUR"],
    ],
}

# Trial balances. Both must balance or the statements workflow refuses to run.
# March 2026 is in EUR; December 2025 is in BGN, so the comparative has to be
# restated — which is the whole point of including it.
TRIAL_BALANCE_2026_03 = {
    "headers": ["Сметка", "Описание", "Дебит", "Кредит"],
    "rows": [
        ["204", "Машини и оборудване", "12 000,00", "0,00"],
        ["241", "Амортизация", "0,00", "3 000,00"],
        ["302", "Материали", "2 500,00", "0,00"],
        ["411", "Клиенти", "8 400,00", "0,00"],
        ["501", "Каса", "600,00", "0,00"],
        ["503", "Разплащателна сметка", "17 500,00", "0,00"],
        ["4531", "ДДС покупки", "1 200,00", "0,00"],
        ["101", "Основен капитал", "0,00", "20 000,00"],
        ["122", "Неразпределена печалба", "0,00", "5 000,00"],
        ["401", "Доставчици", "0,00", "6 200,00"],
        ["421", "Персонал", "0,00", "1 800,00"],
        ["4532", "ДДС продажби", "0,00", "2 400,00"],
        ["452", "Данък върху печалбата", "0,00", "800,00"],
        ["701", "Приходи от продажби", "0,00", "24 000,00"],
        ["602", "Разходи за външни услуги", "14 000,00", "0,00"],
        ["604", "Разходи за заплати", "6 000,00", "0,00"],
        ["603", "Разходи за амортизации", "1 000,00", "0,00"],
    ],
}

TRIAL_BALANCE_2025_12 = {
    "headers": ["Сметка", "Описание", "Дебит", "Кредит"],
    "rows": [
        ["204", "Машини и оборудване", "19 558,30", "0,00"],
        ["241", "Амортизация", "0,00", "3 911,66"],
        ["302", "Материали", "3 911,66", "0,00"],
        ["411", "Клиенти", "11 734,98", "0,00"],
        ["501", "Каса", "977,92", "0,00"],
        ["503", "Разплащателна сметка", "23 469,96", "0,00"],
        ["4531", "ДДС покупки", "1 955,83", "0,00"],
        ["101", "Основен капитал", "0,00", "39 116,60"],
        ["122", "Неразпределена печалба", "0,00", "7 823,32"],
        ["401", "Доставчици", "0,00", "9 779,15"],
        ["421", "Персонал", "0,00", "2 933,75"],
        ["4532", "ДДС продажби", "0,00", "3 911,66"],
        ["452", "Данък върху печалбата", "0,00", "1 564,66"],
        ["701", "Приходи от продажби", "0,00", "39 116,60"],
        ["602", "Разходи за външни услуги", "23 469,96", "0,00"],
        ["604", "Разходи за заплати", "21 000,00", "0,00"],
        ["603", "Разходи за амортизации", "2 078,79", "0,00"],
    ],
}

# A bank statement for March 2026, to reconcile against ledger-2026-03.xlsx.
# Deliberately imperfect: value dates lag, narration is truncated and uppercased
# the way bank exports are, one ledger row never reaches the bank, and the bank
# shows a charge the ledger never recorded.
BANK_STATEMENT = {
    "headers": ["Дата", "Основание", "Сума", "Валута"],
    "rows": [
        ["01.03.2026", "ПЛАЩАНЕ АЛФА ООД ФАКТ 1001", "1 500,00", "EUR"],
        ["04.03.2026", "АЛФА ООД ДОП УСЛУГИ", "375,00", "EUR"],
        ["05.03.2026", "ХОТЕЛ РОДИНА АД КОМАНДИРОВКА", "450,00", "EUR"],
        ["09.03.2026", "БЕТА ЕООД НАЕМ МАРТ", "410,00", "EUR"],
        ["13.03.2026", "EPSILON EOOD SOFTWARE", "1 234,00", "EUR"],
        ["20.03.2026", "БЕТА ЕООД НАЕМ СКЛАД", "205,00", "EUR"],
        ["23.03.2026", "ПРЕВОД БЕЗ ОПИСАНИЕ", "205,00", "EUR"],
        ["26.03.2026", "ЙОТА ЕООД РЕМОНТ", "1 049,99", "EUR"],
        # A bank charge the ledger never recorded.
        ["31.03.2026", "БАНКОВА ТАКСА ОБСЛУЖВАНЕ", "12,50", "EUR"],
    ],
}


def write_workbook(path: Path, spec: dict) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ledger"
    sheet.append(spec["headers"])
    for row in spec["rows"]:
        sheet.append(row)
    workbook.save(path)
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_workbook(OUT_DIR / "ledger-2025-12.xlsx", DECEMBER)
    write_workbook(OUT_DIR / "ledger-2026-01.xlsx", JANUARY)
    write_workbook(OUT_DIR / "ledger-2026-02.xlsx", FEBRUARY)
    write_workbook(OUT_DIR / "ledger-2026-03.xlsx", MARCH)
    write_workbook(OUT_DIR / "ledger-2026-q1-large.xlsx", build_q1_large())
    write_workbook(OUT_DIR / "journal-2026-03.xlsx", JOURNAL)
    write_workbook(OUT_DIR / "trial-balance-2026-03.xlsx", TRIAL_BALANCE_2026_03)
    write_workbook(OUT_DIR / "trial-balance-2025-12.xlsx", TRIAL_BALANCE_2025_12)
    write_workbook(OUT_DIR / "bank-2026-03.xlsx", BANK_STATEMENT)


if __name__ == "__main__":
    main()
