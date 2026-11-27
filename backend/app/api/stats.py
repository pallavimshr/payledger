"""Aggregated numbers for the dashboard overview."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.ledger import account_balances
from app.models import JournalEntry, Order, WebhookEvent
from app.webhooks.inbox import process_pending

router = APIRouter(tags=["dashboard"])


@router.get("/stats")
def stats(session: Session = Depends(get_session)):
    balances = {a.code: bal for a, bal in account_balances(session)}
    orders_by_status = dict(session.execute(select(Order.status, func.count()).group_by(Order.status)).all())
    webhooks_by_status = dict(
        session.execute(select(WebhookEvent.status, func.count()).group_by(WebhookEvent.status)).all()
    )
    refunded = session.scalar(select(func.coalesce(func.sum(Order.amount_refunded_paise), 0)))
    return {
        "revenue_paise": balances.get("revenue:sales", 0),
        "fees_paise": balances.get("expenses:gateway_fees", 0),
        "gateway_held_paise": balances.get("assets:razorpay_clearing", 0)
        + balances.get("assets:stripe_clearing", 0),
        "bank_paise": balances.get("assets:bank", 0),
        "refunded_paise": int(refunded),
        "journal_entries": session.scalar(select(func.count()).select_from(JournalEntry)),
        "orders_total": sum(orders_by_status.values()),
        "orders_by_status": orders_by_status,
        "webhooks_by_status": webhooks_by_status,
    }


@router.post("/webhook-events/retry")
def retry_webhooks(session: Session = Depends(get_session)):
    """Same as `make retry`: reprocess failed/pending events once."""
    return {"result": process_pending(session)}
