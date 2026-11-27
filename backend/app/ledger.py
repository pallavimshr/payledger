"""Ledger service: the only place that writes journal entries.

Every write goes through post_entry(), which calls validate_entry() first.
If validation fails, nothing is written.
"""
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Account, AccountType, Direction, JournalEntry, Posting


@dataclass(frozen=True)
class PostingLine:
    account_code: str
    direction: Direction
    amount_paise: int


class LedgerError(ValueError):
    """Base class for all ledger rule violations."""


class InvalidPostingError(LedgerError):
    """A single line is malformed (e.g. zero or negative amount)."""


class UnbalancedEntryError(LedgerError):
    """Total debits do not equal total credits."""


class UnknownAccountError(LedgerError):
    """A line refers to an account code that doesn't exist."""


def validate_entry(lines: Sequence[PostingLine]) -> None:
    """Raise a LedgerError if this entry would break the books. Returns None if valid.

    Rules:
      1. At least 2 lines (money must move FROM somewhere TO somewhere).
      2. Every amount is a positive int, in paise. Bools are rejected because
         in Python True == 1 and isinstance(True, int) is True.
      3. Total debits == total credits.
    """
    if len(lines) < 2:
        raise InvalidPostingError("An entry needs at least 2 lines")

    total_debit = 0
    total_credit = 0
    for i, line in enumerate(lines, start=1):
        amount = line.amount_paise
        if type(amount) is not int:  # exact check: rejects bool, float, str, None
            raise InvalidPostingError(f"Line {i}: amount must be an integer number of paise")
        if amount <= 0:
            raise InvalidPostingError(f"Line {i}: amount must be greater than zero")

        if line.direction == Direction.DEBIT:
            total_debit += amount
        else:
            total_credit += amount

    if total_debit != total_credit:
        raise UnbalancedEntryError(
            f"Debits ({total_debit}) must equal credits ({total_credit})"
        )


def post_entry(
    session: Session,
    description: str,
    lines: Sequence[PostingLine],
    idempotency_key: str | None = None,
    commit: bool = True,
) -> JournalEntry:
    """Validate and save one journal entry atomically (all lines or none).

    commit=False lets a caller (e.g. the webhook processor) include this entry
    in a bigger transaction and commit everything together.
    """
    validate_entry(lines)

    codes = {line.account_code for line in lines}
    accounts = {
        a.code: a for a in session.scalars(select(Account).where(Account.code.in_(codes)))
    }
    missing = codes - accounts.keys()
    if missing:
        raise UnknownAccountError(f"Unknown account(s): {', '.join(sorted(missing))}")

    entry = JournalEntry(description=description, idempotency_key=idempotency_key)
    for line in lines:
        entry.postings.append(
            Posting(
                account_id=accounts[line.account_code].id,
                direction=line.direction.value,
                amount_paise=line.amount_paise,
            )
        )
    session.add(entry)
    if commit:
        session.commit()
        session.refresh(entry)
    else:
        session.flush()
    return entry


# Assets and expenses grow with debits; everything else grows with credits.
DEBIT_NORMAL = {AccountType.ASSET.value, AccountType.EXPENSE.value}


def account_balances(session: Session) -> list[tuple[Account, int]]:
    """Every account with its balance in paise, signed by its normal side."""
    debits = func.coalesce(
        func.sum(case((Posting.direction == Direction.DEBIT.value, Posting.amount_paise), else_=0)), 0
    )
    credits = func.coalesce(
        func.sum(case((Posting.direction == Direction.CREDIT.value, Posting.amount_paise), else_=0)), 0
    )
    rows = session.execute(
        select(Account, debits, credits)
        .outerjoin(Posting, Posting.account_id == Account.id)
        .group_by(Account.id)
        .order_by(Account.code)
    ).all()
    return [
        (acct, int(d) - int(c) if acct.type in DEBIT_NORMAL else int(c) - int(d))
        for acct, d, c in rows
    ]
