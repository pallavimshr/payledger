"""Order state machine.

            ┌──────────► cancelled
            │
  created ──┼──► paid ──► partially_refunded ──► refunded
            │     ▲               │  ▲                ▲
            ▼     │               └──┘ (more refunds) │
          failed ─┘ (customer retries payment)        │
                          paid ───────────────────────┘ (full refund at once)

Only transitions listed in ALLOWED can happen. Anything else (refunding an
unpaid order, paying a cancelled one) raises InvalidTransitionError.
Every change is written to order_events, so the full history is auditable.
"""
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, OrderEvent, OrderStatus, Refund

S = OrderStatus
ALLOWED: dict[S, set[S]] = {
    S.CREATED: {S.PAID, S.FAILED, S.CANCELLED},
    S.FAILED: {S.PAID, S.FAILED, S.CANCELLED},
    S.PAID: {S.PARTIALLY_REFUNDED, S.REFUNDED},
    S.PARTIALLY_REFUNDED: {S.PARTIALLY_REFUNDED, S.REFUNDED},
    S.REFUNDED: set(),
    S.CANCELLED: set(),
}
PAID_STATES = {S.PAID, S.PARTIALLY_REFUNDED, S.REFUNDED}


class OrderError(ValueError):
    pass


class InvalidTransitionError(OrderError):
    pass


class OverRefundError(OrderError):
    pass


def transition(session: Session, order: Order, to: S, note: str) -> None:
    current = S(order.status)
    if to not in ALLOWED[current]:
        raise InvalidTransitionError(f"Order {order.external_id}: cannot go from {current} to {to}")
    session.add(OrderEvent(order_id=order.id, from_status=current.value, to_status=to.value, note=note))
    order.status = to.value


def add_note(session: Session, order: Order, note: str) -> None:
    """Record an incident without changing status (e.g. a duplicate payment)."""
    session.add(OrderEvent(order_id=order.id, from_status=order.status, to_status=order.status, note=note))


def create_order(session: Session, external_id: str, amount_paise: int) -> Order:
    # Later this calls Razorpay's Orders API; for now we generate a local id.
    order = Order(
        external_id=external_id,
        amount_paise=amount_paise,
        gateway_order_id=f"order_{secrets.token_hex(7)}",
    )
    session.add(order)
    session.flush()
    session.add(OrderEvent(order_id=order.id, from_status=None, to_status=S.CREATED.value,
                           note="Order created"))
    return order


def _locked(session: Session, *where) -> Order | None:
    """Load an order with SELECT ... FOR UPDATE.

    The row lock makes concurrent webhooks for the same order wait for each other,
    so two refunds arriving together can't both see "₹700 still refundable".
    """
    return session.scalars(select(Order).where(*where).with_for_update()).first()


# ---- Effects triggered by gateway events (run inside the webhook transaction) ----

def on_payment_captured(session: Session, gateway_order_id: str | None, payment_id: str, amount: int) -> None:
    if not gateway_order_id:
        return
    order = _locked(session, Order.gateway_order_id == gateway_order_id)
    if order is None:
        return  # payment not linked to an order we track; the ledger still records it
    if S(order.status) in PAID_STATES:
        if order.gateway_payment_id != payment_id:
            add_note(session, order, f"Second payment {payment_id} received for an already-paid order; refund needed")
        return  # same payment seen again: nothing to do
    order.gateway_payment_id = payment_id
    transition(session, order, S.PAID, f"Payment {payment_id} captured")
    if amount != order.amount_paise:
        add_note(session, order, f"Amount mismatch: paid {amount}, expected {order.amount_paise}")


def on_payment_failed(session: Session, gateway_order_id: str | None, payment_id: str, reason: str) -> None:
    if not gateway_order_id:
        return
    order = _locked(session, Order.gateway_order_id == gateway_order_id)
    if order is None or S(order.status) not in (S.CREATED, S.FAILED):
        return  # a late failure of an old attempt must not un-pay a paid order
    transition(session, order, S.FAILED, f"Payment {payment_id} failed: {reason}")


def on_refund_processed(session: Session, payment_id: str | None, refund_id: str, amount: int) -> None:
    if not payment_id:
        return
    order = _locked(session, Order.gateway_payment_id == payment_id)
    if order is None:
        return
    if session.scalar(select(Refund.id).where(Refund.gateway_refund_id == refund_id)):
        return  # already applied
    remaining = order.amount_paise - order.amount_refunded_paise
    if amount > remaining:
        raise OverRefundError(
            f"Refund {refund_id} of {amount} exceeds refundable {remaining} on order {order.external_id}"
        )
    session.add(Refund(order_id=order.id, gateway_refund_id=refund_id, amount_paise=amount))
    order.amount_refunded_paise += amount
    to = S.REFUNDED if order.amount_refunded_paise == order.amount_paise else S.PARTIALLY_REFUNDED
    transition(session, order, to, f"Refund {refund_id} of {amount} paise processed")


def cancel_order(session: Session, order: Order) -> None:
    transition(session, order, S.CANCELLED, "Cancelled by merchant")
