"""The webhook inbox: store first, process second, retry on failure.

Why this design gives exactly-once *effects* even though gateways deliver
webhooks at-least-once (they retry until they get a 2xx, so duplicates happen):

  1. record_event()  inserts the raw event. A unique (provider, event_id)
                     constraint rejects duplicates at the database level, which
                     is safe even when two copies arrive at the same millisecond.
  2. process_event() writes the journal entry AND marks the event processed in
                     ONE transaction. If the server crashes halfway, the database
                     rolls both back and the event stays "received" for a retry.
  3. Every journal entry also has an idempotency_key per business fact
     (e.g. razorpay:payment:pay_123). So even if Razorpay sent the same payment
     under two different event ids, it is posted once.
"""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ledger import post_entry
from app.models import JournalEntry, WebhookEvent, WebhookStatus, utcnow
from app.webhooks import razorpay

MAX_ATTEMPTS = 5
PROVIDER_HANDLERS = {"razorpay": razorpay.HANDLERS}
PROVIDER_ORDER_EFFECTS = {"razorpay": razorpay.ORDER_EFFECTS}


def record_event(
    session: Session, provider: str, event_id: str, event_type: str, payload: dict
) -> tuple[WebhookEvent | None, bool]:
    """Save the event. Returns (event, is_duplicate)."""
    event = WebhookEvent(
        provider=provider, event_id=event_id, event_type=event_type, payload=payload
    )
    session.add(event)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return None, True
    return event, False


def process_event(session: Session, event: WebhookEvent) -> WebhookEvent:
    """Turn one stored event into a journal entry. Never raises; records failures."""
    event_pk = event.id
    try:
        handler = PROVIDER_HANDLERS[event.provider].get(event.event_type)
        order_effect = PROVIDER_ORDER_EFFECTS[event.provider].get(event.event_type)
        if handler is None and order_effect is None:
            event.status = WebhookStatus.IGNORED.value
        else:
            if handler is not None:
                spec = handler(event.payload)
                already_posted = session.scalar(
                    select(JournalEntry.id).where(JournalEntry.idempotency_key == spec.idempotency_key)
                )
                if not already_posted:
                    post_entry(session, spec.description, spec.lines, spec.idempotency_key, commit=False)
            if order_effect is not None:
                order_effect(session, event.payload)  # may raise, e.g. OverRefundError
            event.status = WebhookStatus.PROCESSED.value
        event.attempts += 1
        event.processed_at = utcnow()
        event.last_error = None
        session.commit()  # ledger entry + order change + event status: all or nothing
    except Exception as exc:  # noqa: BLE001 - we want to record ANY failure
        session.rollback()
        event = session.get(WebhookEvent, event_pk)
        event.attempts += 1
        event.status = WebhookStatus.FAILED.value
        event.last_error = f"{type(exc).__name__}: {exc}"[:2000]
        session.commit()
    return event


def process_pending(session: Session) -> dict[str, int]:
    """Retry everything not yet processed (used by the worker)."""
    pending = session.scalars(
        select(WebhookEvent)
        .where(
            WebhookEvent.status.in_([WebhookStatus.RECEIVED.value, WebhookStatus.FAILED.value]),
            WebhookEvent.attempts < MAX_ATTEMPTS,
        )
        .order_by(WebhookEvent.received_at)
    ).all()
    counts: dict[str, int] = {}
    for event in pending:
        status = process_event(session, event).status
        counts[status] = counts.get(status, 0) + 1
    return counts
