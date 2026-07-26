"""Chart of accounts: account code -> statement line.

Treated as data, not code. The shipped codes are illustrative and meant to be
replaced with the firm's actual сметкоплан — see the warning in config/coa.yaml.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from iconomics.config import ConfigError, find_config_dir

PROFIT_AND_LOSS = "profit_and_loss"
BALANCE_SHEET = "balance_sheet"


class CoaError(ConfigError):
    """Raised when config/coa.yaml is missing or malformed."""


@dataclass(frozen=True)
class Account:
    code: str
    name: str
    statement: str
    line: str
    side: str
    cash: bool = False


@dataclass(frozen=True)
class Coa:
    accounts: dict[str, Account]
    line_order: dict[str, list[str]]

    def get(self, code: str) -> Account | None:
        """Resolve a code, falling back to its parent for sub-accounts.

        A firm that books to 6021 rather than 602 should still roll up correctly,
        so lookup walks the code down one character at a time.
        """
        key = (code or "").strip()
        while key:
            if key in self.accounts:
                return self.accounts[key]
            key = key[:-1]
        return None

    def ordered_lines(self, statement: str) -> list[str]:
        return list(self.line_order.get(statement, []))

    def cash_accounts(self) -> list[str]:
        return sorted(code for code, a in self.accounts.items() if a.cash)


def load_coa(config_dir: Path | None = None) -> Coa:
    directory = config_dir if config_dir is not None else find_config_dir()
    path = Path(directory) / "coa.yaml"
    if not path.is_file():
        raise CoaError(f"missing config file: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("accounts") or {}
    if not entries:
        raise CoaError(f"{path} defines no accounts")

    accounts: dict[str, Account] = {}
    for code, spec in entries.items():
        statement = str(spec.get("statement", "")).strip()
        if statement not in (PROFIT_AND_LOSS, BALANCE_SHEET):
            raise CoaError(
                f"{path}: account {code} has statement {statement!r}; "
                f"expected {PROFIT_AND_LOSS} or {BALANCE_SHEET}"
            )
        side = str(spec.get("side", "")).strip()
        if side not in ("debit", "credit"):
            raise CoaError(
                f"{path}: account {code} has side {side!r}; expected debit or credit"
            )
        accounts[str(code).strip()] = Account(
            code=str(code).strip(),
            name=str(spec.get("name", "")).strip(),
            statement=statement,
            line=str(spec.get("line", "")).strip(),
            side=side,
            cash=bool(spec.get("cash", False)),
        )

    order = raw.get("line_order") or {}
    line_order = {
        key: [str(item) for item in (order.get(key) or [])]
        for key in (PROFIT_AND_LOSS, BALANCE_SHEET)
    }
    return Coa(accounts=accounts, line_order=line_order)
