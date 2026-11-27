"""Database tables for the double-entry ledger.

Three tables:
  accounts         - buckets money can sit in (bank, gateway clearing, revenue, fees...)
  journal_entries  - one business event (a payment, a refund, a payout)
  postings         - the lines of an entry: "debit X paise to account A"

Rule enforced by the ledger service: for every journal entry,
total debits == total credits. Money is never created or destroyed,
only moved between accounts.

Money is stored as integer paise (₹1 = 100 paise), never floats,
because 0.1 + 0.2 != 0.3 in floating point.
"""
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class AccountType(StrEnum):
    ASSET = "asset"          # what we own: bank, money held by Razorpay
    LIABILITY = "liability"  # what we owe: refunds due to customers
    EQUITY = "equity"        # owner's stake
    REVENUE = "revenue"      # income: sales
    EXPENSE = "expense"      # costs: gateway fees


class Direction(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(
            "type IN ('asset','liability','equity','revenue','expense')", name="ck_account_type"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    description: Mapped[str] = mapped_column(String(500))
    # Used later for exactly-once webhook processing: the same key can never be posted twice.
    idempotency_key: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    postings: Mapped[list["Posting"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", lazy="selectin"
    )


class Posting(Base):
    __tablename__ = "postings"
    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="ck_posting_amount_positive"),
        CheckConstraint("direction IN ('debit','credit')", name="ck_posting_direction"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journal_entries.id"), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    direction: Mapped[str] = mapped_column(String(6))
    amount_paise: Mapped[int] = mapped_column(BigInteger)

    entry: Mapped[JournalEntry] = relationship(back_populates="postings")
    account: Mapped[Account] = relationship(lazy="joined")


class WebhookStatus(StrEnum):
    RECEIVED = "received"    # stored, not processed yet
    PROCESSED = "processed"  # journal entry written
    IGNORED = "ignored"      # event type we don't handle (e.g. payment.authorized)
    FAILED = "failed"        # processing errored; the worker will retry it


class WebhookEvent(Base):
    """The webhook "inbox": every incoming event is saved here BEFORE we act on it.

    The unique (provider, event_id) constraint is what makes duplicates harmless:
    if Razorpay sends the same event twice, the second insert fails and we skip it.
    """
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_webhook_provider_event"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(20))
    event_id: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    status: Mapped[str] = mapped_column(String(20), default=WebhookStatus.RECEIVED.value, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
