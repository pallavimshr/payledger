"""Deterministic matching: report rows vs ledger entries. No AI here.

Money correctness must be exact and repeatable, so classification is plain code.
The AI only explains the rows this module flags.

Each Razorpay ledger entry has an idempotency key like
  razorpay:payment:pay_123   razorpay:refund:rfnd_456
which is how a report row finds "its" entry.
"""
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import JournalEntry, ReconciliationItem, ReconStatus as RS
from app.recon.report import ReportRow


@dataclass
class LedgerFacts:
    entry: JournalEntry
    amount_paise: int   # sale (payment) or refunded amount
    fee_paise: int      # gateway fee booked on the payment (0 for refunds)


def ledger_facts(entry: JournalEntry) -> LedgerFacts:
    amount = fee = 0
    for p in entry.postings:
        code = p.account.code
        if code == "revenue:sales":
            amount += p.amount_paise  # credit for payments, debit for refunds
        elif code == "expenses:gateway_fees" and p.direction == "debit":
            fee += p.amount_paise
    return LedgerFacts(entry, amount, fee)


def sort_key(dt: datetime) -> datetime:
    """Comparable timestamp whether the DB returned it tz-aware (Postgres) or naive (SQLite)."""
    return dt.astimezone(UTC).replace(tzinfo=None) if dt.tzinfo else dt


def razorpay_entries(session: Session) -> dict[str, JournalEntry]:
    """All Razorpay payment/refund entries, keyed by idempotency key."""
    q = select(JournalEntry).where(
        JournalEntry.idempotency_key.like("razorpay:payment:%")
        | JournalEntry.idempotency_key.like("razorpay:refund:%")
    )
    return {e.idempotency_key: e for e in session.scalars(q)}


def already_matched_keys(session: Session) -> set[str]:
    """Entries matched in an earlier run: they were settled before, not 'missing' now."""
    rows = session.execute(
        select(ReconciliationItem.entity_type, ReconciliationItem.entity_id)
        .where(ReconciliationItem.status == RS.MATCHED.value)
    ).all()
    return {f"razorpay:{t}:{i}" for t, i in rows}


def match(session: Session, rows: list[ReportRow]) -> list[ReconciliationItem]:
    entries = razorpay_entries(session)
    seen_keys: set[str] = set()
    items: list[ReconciliationItem] = []

    for row in rows:
        key = f"razorpay:{row.type}:{row.entity_id}"
        item = ReconciliationItem(
            entity_type=row.type, entity_id=row.entity_id,
            report_amount_paise=row.amount_paise, report_fee_paise=row.fee_paise,
            report_row=row.raw,
        )
        entry = entries.get(key)
        if entry is None:
            item.status = RS.MISSING_IN_LEDGER.value   # includes all adjustments
        else:
            seen_keys.add(key)
            facts = ledger_facts(entry)
            item.journal_entry_id = entry.id
            item.ledger_amount_paise = facts.amount_paise
            item.ledger_fee_paise = facts.fee_paise if row.type == "payment" else None
            if facts.amount_paise != row.amount_paise:
                item.status = RS.AMOUNT_MISMATCH.value
            elif row.type == "payment" and facts.fee_paise != row.fee_paise:
                item.status = RS.FEE_MISMATCH.value
            else:
                item.status = RS.MATCHED.value
        items.append(item)

    # Ledger entries the gateway didn't report (and that no earlier report covered).
    done = already_matched_keys(session)
    for key, entry in sorted(entries.items(), key=lambda kv: sort_key(kv[1].created_at)):
        if key in seen_keys or key in done:
            continue
        _, kind, entity_id = key.split(":", 2)
        facts = ledger_facts(entry)
        items.append(ReconciliationItem(
            entity_type=kind, entity_id=entity_id, status=RS.MISSING_IN_REPORT.value,
            journal_entry_id=entry.id, ledger_amount_paise=facts.amount_paise,
            ledger_fee_paise=facts.fee_paise if kind == "payment" else None,
        ))

    for pos, item in enumerate(items):
        item.position = pos
        item.resolution = "none" if item.status == RS.MATCHED.value else "open"
    return items
