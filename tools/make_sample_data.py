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


if __name__ == "__main__":
    main()
