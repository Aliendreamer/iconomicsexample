"""Trial balance -> profit and loss, balance sheet, and comparatives.

Two invariants are enforced rather than hoped for:

  * The trial balance must balance before anything is produced. An unbalanced
    input is a structural failure, not a row-level problem.
  * The balance sheet must balance after. If it does not, the account mapping is
    wrong, and emitting the statement anyway would hide that.

**All internal arithmetic is debit-positive** (``debit - credit``). Aggregating in
the account's "natural" direction instead would break any statement line fed by
accounts with opposite normal sides — a receivable and a payable rolling into one
line would add rather than offset. Direction is applied only for presentation, so
revenue and liabilities still read positive on the face of the statement.

A statutory cash flow statement is NOT produced. Deriving one requires movement
analysis, not a single trial balance. When a prior period is supplied, a cash
movement summary is produced instead and labelled as such — see CASH_NOTE.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from iconomics.coa import BALANCE_SHEET, PROFIT_AND_LOSS, Coa, load_coa
from iconomics.money import Money
from iconomics.workbook import Problem, Sheet, TrialBalance, TrialLine

PNL_COLUMNS = ["Line", "Current Period", "Prior Period", "Change"]
BS_COLUMNS = ["Line", "Section", "Current Period", "Prior Period", "Change"]
CASH_COLUMNS = ["Account", "Name", "Opening", "Closing", "Movement"]
UNMAPPED_COLUMNS = ["Source Row", "Account", "Reason"]
CHECK_COLUMNS = ["Check", "Result", "Detail"]

MONEY_FORMATS = {
    "Current Period": "0.00",
    "Prior Period": "0.00",
    "Change": "0.00",
    "Opening": "0.00",
    "Closing": "0.00",
    "Movement": "0.00",
}

CASH_NOTE = (
    "Cash movement summary — NOT a statutory cash flow statement. Derived from "
    "the change in cash account balances between the two trial balances supplied. "
    "A statutory statement requires movement analysis."
)

RESULT_LINE = "Финансов резултат за периода"
ASSETS_LINE = "Общо активи"
EQUITY_LIABILITIES_LINE = "Общо собствен капитал и задължения"


class Unbalanced(RuntimeError):
    """Raised when a trial balance does not balance, or the output does not."""


@dataclass(frozen=True)
class Statements:
    pnl: dict[str, Money]
    balance_sheet: dict[str, Money]
    prior_pnl: dict[str, Money]
    prior_balance_sheet: dict[str, Money]
    cash: list[tuple[str, str, Money, Money]]
    unmapped: list[Problem]
    result: Money
    prior_result: Money
    assets: Money
    equity_and_liabilities: Money
    currency: str
    coa: Coa
    has_prior: bool = False
    checks: dict[str, bool] = field(default_factory=dict)


def _zero(currency: str) -> Money:
    return Money(Decimal("0.00"), currency)


def restate_trial_balance(
    balance: TrialBalance, target_currency: str
) -> TrialBalance:
    """Convert every balance to the target currency at the fixed rate.

    This is how a 2025 BGN trial balance becomes usable as a comparative against
    2026 EUR figures. Conversion is from the originally recorded amount, never
    chained, so it cannot drift.
    """
    convert = (
        (lambda m: m.to_eur()) if target_currency == "EUR" else (lambda m: m.to_bgn())
    )
    return TrialBalance(
        lines=[
            TrialLine(
                source_row=line.source_row,
                account=line.account,
                name=line.name,
                debit=convert(line.debit),
                credit=convert(line.credit),
            )
            for line in balance.lines
        ],
        problems=list(balance.problems),
        source_path=balance.source_path,
    )


def _totals(balance: TrialBalance, currency: str):
    debits = _zero(currency)
    credits = _zero(currency)
    for line in balance.lines:
        debits = debits + line.debit
        credits = credits + line.credit
    return debits, credits


def _roll_up(balance: TrialBalance, coa: Coa, currency: str):
    """Aggregate trial balance lines onto statement lines, debit-positive."""
    pnl: dict[str, Money] = {}
    bs: dict[str, Money] = {}
    cash: list[tuple[str, str, Money, Money]] = []
    unmapped: list[Problem] = []

    for line in balance.lines:
        account = coa.get(line.account)
        if account is None:
            unmapped.append(
                Problem(
                    line.source_row,
                    "account",
                    line.account,
                    "not in config/coa.yaml; add it or correct the code",
                )
            )
            continue

        signed = line.debit - line.credit
        target = pnl if account.statement == PROFIT_AND_LOSS else bs
        target[account.line] = target.get(account.line, _zero(currency)) + signed

        if account.cash:
            cash.append((account.code, account.name or line.name, line.debit, line.credit))

    return pnl, bs, cash, unmapped


def _line_side(line_name: str, coa: Coa) -> str:
    """The normal side of the accounts mapped to this statement line.

    Resolved from the lexicographically smallest account code on the line, not
    from iteration order. JavaScript objects reorder integer-like keys ("101",
    "204") numerically while Python dicts keep YAML order, so anything depending
    on iteration order would diverge between the two implementations.
    """
    for code in sorted(coa.accounts):
        account = coa.accounts[code]
        if account.line == line_name:
            return account.side
    return "debit"


def _display(line_name: str, signed: Money, coa: Coa) -> Money:
    """Flip credit-natured lines so revenue and liabilities read positive."""
    if _line_side(line_name, coa) == "credit":
        return _zero(signed.currency) - signed
    return signed


def _result_from(pnl: dict[str, Money], currency: str) -> Money:
    """Revenue less expenses.

    Debit-positive means expenses are positive and revenue negative, so the
    period result is simply the negated sum.
    """
    total = _zero(currency)
    for amount in pnl.values():
        total = total + amount
    return _zero(currency) - total


def _pair_cash(current, prior, currency: str):
    prior_by_code = {code: (debit - credit) for code, _, debit, credit in prior}
    return [
        (code, name, prior_by_code.get(code, _zero(currency)), debit - credit)
        for code, name, debit, credit in sorted(current)
    ]


def build(
    current: TrialBalance,
    prior: TrialBalance | None = None,
    currency: str = "EUR",
) -> Statements:
    """Roll a trial balance up into statements, with comparatives if supplied."""
    coa = load_coa()

    debits, credits = _totals(current, currency)
    if debits != credits:
        raise Unbalanced(
            f"trial balance does not balance: debits {debits} vs credits {credits}. "
            "Nothing was written — a half-correct statement is worse than none."
        )

    pnl, bs, cash_lines, unmapped = _roll_up(current, coa, currency)
    result = _result_from(pnl, currency)

    prior_pnl: dict[str, Money] = {}
    prior_bs: dict[str, Money] = {}
    prior_cash: list = []
    prior_result = _zero(currency)

    if prior is not None:
        prior_debits, prior_credits = _totals(prior, currency)
        if prior_debits != prior_credits:
            raise Unbalanced(
                f"prior trial balance does not balance: debits {prior_debits} vs "
                f"credits {prior_credits}"
            )
        prior_pnl, prior_bs, prior_cash, _ = _roll_up(prior, coa, currency)
        prior_result = _result_from(prior_pnl, currency)

    assets = _zero(currency)
    equity_and_liabilities = _zero(currency)
    for line_name, signed in bs.items():
        if _line_side(line_name, coa) == "debit":
            assets = assets + signed
        else:
            equity_and_liabilities = equity_and_liabilities + (_zero(currency) - signed)

    balances = assets == equity_and_liabilities + result
    if not balances:
        raise Unbalanced(
            f"balance sheet does not balance: assets {assets} vs equity and "
            f"liabilities {equity_and_liabilities} plus result {result} "
            f"(difference {assets - equity_and_liabilities - result}). "
            "This usually means an account is mapped to the wrong statement or "
            "side in config/coa.yaml. Nothing was written."
        )

    return Statements(
        pnl=pnl,
        balance_sheet=bs,
        prior_pnl=prior_pnl,
        prior_balance_sheet=prior_bs,
        cash=_pair_cash(cash_lines, prior_cash, currency),
        unmapped=unmapped,
        result=result,
        prior_result=prior_result,
        assets=assets,
        equity_and_liabilities=equity_and_liabilities,
        currency=currency,
        coa=coa,
        has_prior=prior is not None,
        checks={"trial_balance_balances": True, "balance_sheet_balances": balances},
    )


def _ordered_names(
    current: dict[str, Money], prior: dict[str, Money], ordered: list[str]
) -> list[str]:
    present = set(current) | set(prior)
    names = [name for name in ordered if name in present]
    names += sorted(present - set(names))
    return names


def to_sheets(result: Statements) -> dict[str, Sheet]:
    """Render statements as sheets. Comparatives are blank without a prior period."""
    blank = "" if not result.has_prior else None

    def rows_for(current, prior, ordered, with_section=False):
        rows = []
        for name in _ordered_names(current, prior, ordered):
            now = _display(name, current.get(name, _zero(result.currency)), result.coa)
            was = _display(name, prior.get(name, _zero(result.currency)), result.coa)
            cells = [name]
            if with_section:
                cells.append(
                    "Активи"
                    if _line_side(name, result.coa) == "debit"
                    else "Собствен капитал и задължения"
                )
            cells += [
                now,
                was if result.has_prior else blank,
                (now - was) if result.has_prior else blank,
            ]
            rows.append(cells)
        return rows

    pnl_rows = rows_for(
        result.pnl, result.prior_pnl, result.coa.ordered_lines(PROFIT_AND_LOSS)
    )
    pnl_rows.append(
        [
            RESULT_LINE,
            result.result,
            result.prior_result if result.has_prior else blank,
            (result.result - result.prior_result) if result.has_prior else blank,
        ]
    )

    bs_rows = rows_for(
        result.balance_sheet,
        result.prior_balance_sheet,
        result.coa.ordered_lines(BALANCE_SHEET),
        with_section=True,
    )
    bs_rows.append([RESULT_LINE, "Собствен капитал и задължения", result.result, blank, blank])
    bs_rows.append([ASSETS_LINE, "Активи", result.assets, blank, blank])
    bs_rows.append(
        [
            EQUITY_LIABILITIES_LINE,
            "Собствен капитал и задължения",
            result.equity_and_liabilities + result.result,
            blank,
            blank,
        ]
    )

    check_rows = [
        [
            "Trial balance balances (debits = credits)",
            "yes" if result.checks.get("trial_balance_balances") else "NO",
            "checked before any output was written",
        ],
        [
            "Balance sheet balances (assets = equity + liabilities + result)",
            "yes" if result.checks.get("balance_sheet_balances") else "NO",
            f"{result.assets} = {result.equity_and_liabilities} + {result.result}",
        ],
        [
            "Comparatives included",
            "yes" if result.has_prior else "no",
            "supply --prior to add a comparative column",
        ],
        [
            "Cash flow statement",
            "no",
            CASH_NOTE,
        ],
    ]

    sheets = {
        "ОПР": Sheet(columns=PNL_COLUMNS, rows=pnl_rows, number_formats=MONEY_FORMATS),
        "Баланс": Sheet(columns=BS_COLUMNS, rows=bs_rows, number_formats=MONEY_FORMATS),
        "Checks": Sheet(columns=CHECK_COLUMNS, rows=check_rows),
    }

    if result.has_prior:
        cash_rows = [
            [code, name, opening, closing, closing - opening]
            for code, name, opening, closing in result.cash
        ]
        sheets["Парични средства"] = Sheet(
            columns=CASH_COLUMNS, rows=cash_rows, number_formats=MONEY_FORMATS
        )

    if result.unmapped:
        sheets["Unmapped Accounts"] = Sheet(
            columns=UNMAPPED_COLUMNS,
            rows=[[p.source_row, p.raw, p.reason] for p in result.unmapped],
        )

    return sheets
