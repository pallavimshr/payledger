"""Webhook endpoints that payment gateways call."""
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.db import get_session
from app.models import WebhookEvent
from app.webhooks.inbox import process_event, record_event
from app.webhooks.razorpay import verify_signature

router = APIRouter(tags=["webhooks"])


def _handle(session: Session, event_id: str, event_type: str, payload: dict) -> dict:
    event, duplicate = record_event(session, "razorpay", event_id, event_type, payload)
    if duplicate:
        return {"status": "duplicate", "event_id": event_id}
    event = process_event(session, event)
    return {"status": event.status, "event_id": event_id}


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, session: Session = Depends(get_session)):
    # Read the RAW bytes: the signature is computed over the exact body Razorpay sent.
    # Parsing to JSON first and re-serializing would change spacing and break the check.
    raw = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not verify_signature(raw, signature, settings.razorpay_webhook_secret):
        raise HTTPException(400, "Invalid signature")

    try:
        payload = json.loads(raw)
        event_type = payload["event"]
    except (ValueError, KeyError):
        raise HTTPException(400, "Malformed payload")

    # Razorpay sends a stable event id; fall back to a hash of the body if missing.
    event_id = request.headers.get("X-Razorpay-Event-Id") or hashlib.sha256(raw).hexdigest()

    # We always answer 200 once the event is safely stored, even if processing
    # failed: our own worker retries it, so Razorpay doesn't need to.
    # DB work is blocking, so run it in a thread instead of the async event loop.
    return await run_in_threadpool(_handle, session, event_id, event_type, payload)


@router.get("/webhook-events")
def list_webhook_events(limit: int = 50, session: Session = Depends(get_session)):
    events = session.scalars(
        select(WebhookEvent).order_by(WebhookEvent.received_at.desc()).limit(min(limit, 200))
    )
    return [
        {
            "event_id": e.event_id, "provider": e.provider, "event_type": e.event_type,
            "status": e.status, "attempts": e.attempts, "last_error": e.last_error,
            "received_at": e.received_at, "processed_at": e.processed_at,
        }
        for e in events
    ]
