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


if __name__ == "__main__":
    main()
