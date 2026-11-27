"""Razorpay-specific logic: signature checks and turning events into ledger entries.

Razorpay docs: https://razorpay.com/docs/webhooks/
  - Header X-Razorpay-Signature = HMAC-SHA256(raw request body, webhook secret), hex
  - Header X-Razorpay-Event-Id  = unique id per event (same id on Razorpay's retries)
"""
import hashlib
import hmac
from dataclasses import dataclass

from app.ledger import PostingLine
from app.models import Direction

D, C = Direction.DEBIT, Direction.CREDIT


def verify_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """True only if the request really came from Razorpay.

    We compute the HMAC ourselves and compare. hmac.compare_digest takes the same
    time whether the first or last character differs, so attackers can't guess
    the signature one character at a time (a "timing attack").
    """
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


@dataclass(frozen=True)
class EntrySpec:
    """What a webhook should write to the ledger."""
    description: str
    idempotency_key: str  # one business fact = one key, e.g. "razorpay:payment:pay_123"
    lines: list[PostingLine]


def _entity(event: dict, name: str) -> dict:
    return event["payload"][name]["entity"]


def _require_inr(entity: dict) -> None:
    if entity.get("currency", "INR") != "INR":
        raise ValueError(f"Unsupported currency {entity.get('currency')}")


def payment_captured(event: dict) -> EntrySpec:
    """Customer paid. Razorpay holds the money minus its fee (fee includes GST).

    ₹1,000 payment, ₹23.60 fee:
      debit  assets:razorpay_clearing   97,640
      debit  expenses:gateway_fees       2,360
      credit revenue:sales             100,000
    """
    p = _entity(event, "payment")
    _require_inr(p)
    amount, fee = int(p["amount"]), int(p.get("fee") or 0)
    lines = [PostingLine("revenue:sales", C, amount)]
    if amount - fee > 0:
        lines.append(PostingLine("assets:razorpay_clearing", D, amount - fee))
    if fee > 0:
        lines.append(PostingLine("expenses:gateway_fees", D, fee))
    return EntrySpec(
        description=f"Razorpay payment {p['id']} captured (order {p.get('order_id') or '-'})",
        idempotency_key=f"razorpay:payment:{p['id']}",
        lines=lines,
    )


def refund_processed(event: dict) -> EntrySpec:
    """Money went back to the customer. Razorpay does not return its fee.

      debit  revenue:sales             (sale reversed)
      credit assets:razorpay_clearing  (Razorpay paid it out of our balance)
    """
    r = _entity(event, "refund")
    _require_inr(r)
    amount = int(r["amount"])
    return EntrySpec(
        description=f"Razorpay refund {r['id']} for payment {r.get('payment_id')}",
        idempotency_key=f"razorpay:refund:{r['id']}",
        lines=[
            PostingLine("revenue:sales", D, amount),
            PostingLine("assets:razorpay_clearing", C, amount),
        ],
    )


def settlement_processed(event: dict) -> EntrySpec:
    """Razorpay transferred our balance to the bank.

      debit  assets:bank
      credit assets:razorpay_clearing
    """
    s = _entity(event, "settlement")
    amount = int(s["amount"])
    return EntrySpec(
        description=f"Razorpay settlement {s['id']} (UTR {s.get('utr') or '-'})",
        idempotency_key=f"razorpay:settlement:{s['id']}",
        lines=[
            PostingLine("assets:bank", D, amount),
            PostingLine("assets:razorpay_clearing", C, amount),
        ],
    )


# Event types we turn into ledger entries. Anything else is stored and marked "ignored".
HANDLERS = {
    "payment.captured": payment_captured,
    "refund.processed": refund_processed,
    "settlement.processed": settlement_processed,
}
