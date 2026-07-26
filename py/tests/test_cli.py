import pytest
from openpyxl import Workbook

from iconomics import cli
from iconomics.config import find_config_dir


def sample(name):
    return str(find_config_dir().parent / "data" / "raw" / name)


def test_cleanup_writes_output_and_reports_zero(tmp_path):
    code = cli.main(["cleanup", "--in", sample("ledger-2026-02.xlsx"), "--out", str(tmp_path)])
    assert code == 0
    assert (tmp_path / "ledger-2026-02-clean.xlsx").is_file()


def test_cleanup_summary_has_the_contracted_format(tmp_path, capsys):
    cli.main(["cleanup", "--in", sample("ledger-2026-02.xlsx"), "--out", str(tmp_path)])
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0] == "cleanup: ledger-2026-02.xlsx"
    assert lines[1] == "  rows in:     6"
    assert lines[2] == "  rows clean:  4"
    assert lines[3] == "  changes:     1"
    assert lines[4] == "  exceptions:  2"
    assert lines[5].startswith("  output:      ")


def test_january_file_converts_both_bgn_rows_net_and_vat(tmp_path, capsys):
    cli.main(["cleanup", "--in", sample("ledger-2026-01.xlsx"), "--out", str(tmp_path)])
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[1] == "  rows in:     5"
    assert lines[2] == "  rows clean:  5"
    # Two BGN rows, each contributing a net and a VAT conversion.
    assert lines[3] == "  changes:     4"
    assert lines[4] == "  exceptions:  0"


def test_december_file_converts_every_row(tmp_path, capsys):
    cli.main(["cleanup", "--in", sample("ledger-2025-12.xlsx"), "--out", str(tmp_path)])
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[2] == "  rows clean:  4"
    # All four rows are pre-euro BGN: four nets plus four VAT amounts.
    assert lines[3] == "  changes:     8"


def test_missing_column_is_exit_code_one(tmp_path, capsys):
    bad = tmp_path / "bad.xlsx"
    workbook = Workbook()
    workbook.active.append(["Дата", "Контрагент"])
    workbook.save(bad)

    code = cli.main(["cleanup", "--in", str(bad), "--out", str(tmp_path)])
    assert code == 1
    assert "amount_net" in capsys.readouterr().err


def test_unknown_subcommand_is_exit_code_two():
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["nonsense"])
    assert exit_info.value.code == 2


def test_invalid_currency_is_exit_code_two(tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(
            [
                "cleanup",
                "--in",
                sample("ledger-2026-02.xlsx"),
                "--out",
                str(tmp_path),
                "--currency",
                "USD",
            ]
        )
    assert exit_info.value.code == 2
