"""Request/response shapes for the API (validated by Pydantic)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models import AccountType, Direction


class AccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100, examples=["assets:bank"])
    name: str = Field(min_length=1, max_length=200, examples=["HDFC current account"])
    type: AccountType


class AccountOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    type: AccountType
    currency: str
    balance_paise: int = 0


class PostingIn(BaseModel):
    account_code: str
    direction: Direction
    amount_paise: int = Field(examples=[100000])


class JournalEntryCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    lines: list[PostingIn]
    idempotency_key: str | None = None


class PostingOut(BaseModel):
    account_code: str
    direction: Direction
    amount_paise: int


class JournalEntryOut(BaseModel):
    id: uuid.UUID
    description: str
    idempotency_key: str | None
    occurred_at: datetime
    lines: list[PostingOut]
