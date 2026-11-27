"""HTTP endpoints. Open http://localhost:8000/docs to try them."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.ledger import LedgerError, PostingLine, account_balances, post_entry
from app.models import Account, JournalEntry, Posting
from app.schemas import (
    AccountCreate,
    AccountOut,
    JournalEntryCreate,
    JournalEntryOut,
    PostingOut,
)

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(session: Session = Depends(get_session)):
    return [
        AccountOut(
            id=a.id, code=a.code, name=a.name, type=a.type, currency=a.currency, balance_paise=bal
        )
        for a, bal in account_balances(session)
    ]


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(body: AccountCreate, session: Session = Depends(get_session)):
    account = Account(code=body.code, name=body.name, type=body.type.value)
    session.add(account)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, f"Account '{body.code}' already exists")
    return AccountOut(
        id=account.id, code=account.code, name=account.name,
        type=account.type, currency=account.currency,
    )


def _entry_out(entry: JournalEntry) -> JournalEntryOut:
    return JournalEntryOut(
        id=entry.id,
        description=entry.description,
        idempotency_key=entry.idempotency_key,
        occurred_at=entry.occurred_at,
        lines=[
            PostingOut(account_code=p.account.code, direction=p.direction, amount_paise=p.amount_paise)
            for p in entry.postings
        ],
    )


@router.get("/journal-entries", response_model=list[JournalEntryOut])
def list_entries(account: str | None = None, limit: int = 50, session: Session = Depends(get_session)):
    """List journal entries, newest first. `account` = only entries touching that account code."""
    query = select(JournalEntry).order_by(JournalEntry.created_at.desc()).limit(min(limit, 200))
    if account:
        query = query.where(
            JournalEntry.postings.any(Posting.account.has(Account.code == account))
        )
    entries = session.scalars(query)
    return [_entry_out(e) for e in entries]


@router.post("/journal-entries", response_model=JournalEntryOut, status_code=201)
def create_entry(body: JournalEntryCreate, session: Session = Depends(get_session)):
    lines = [PostingLine(l.account_code, l.direction, l.amount_paise) for l in body.lines]
    try:
        entry = post_entry(session, body.description, lines, body.idempotency_key)
    except LedgerError as e:
        session.rollback()
        raise HTTPException(422, str(e))
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "An entry with this idempotency_key already exists")
    return _entry_out(entry)
