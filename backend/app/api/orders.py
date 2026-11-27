"""Order endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Order
from app.orders import InvalidTransitionError, cancel_order, create_order
from app.schemas import OrderCreate, OrderDetail, OrderEventOut, OrderOut, RefundOut

router = APIRouter(tags=["orders"])


def _out(o: Order) -> dict:
    return dict(
        id=o.id, external_id=o.external_id, amount_paise=o.amount_paise,
        amount_refunded_paise=o.amount_refunded_paise,
        refundable_paise=o.amount_paise - o.amount_refunded_paise,
        currency=o.currency, status=o.status, gateway_order_id=o.gateway_order_id,
        gateway_payment_id=o.gateway_payment_id, created_at=o.created_at,
    )


def _detail(o: Order) -> OrderDetail:
    return OrderDetail(
        **_out(o),
        history=[OrderEventOut(from_status=e.from_status, to_status=e.to_status, note=e.note,
                               created_at=e.created_at) for e in o.history],
        refunds=[RefundOut(gateway_refund_id=r.gateway_refund_id, amount_paise=r.amount_paise,
                           created_at=r.created_at) for r in o.refunds],
    )


def _get(session: Session, order_id: uuid.UUID) -> Order:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Order not found")
    return order


@router.post("/orders", response_model=OrderDetail, status_code=201)
def create(body: OrderCreate, session: Session = Depends(get_session)):
    try:
        order = create_order(session, body.external_id, body.amount_paise)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, f"Order '{body.external_id}' already exists")
    session.refresh(order)
    return _detail(order)


@router.get("/orders", response_model=list[OrderOut])
def list_orders(
    status: str | None = None,
    q: str | None = None,
    limit: int = 50,
    session: Session = Depends(get_session),
):
    """List orders. `q` searches order number, gateway order id and payment id."""
    query = select(Order).order_by(Order.created_at.desc()).limit(min(limit, 200))
    if status:
        query = query.where(Order.status == status)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.where(or_(
            Order.external_id.ilike(term),
            Order.gateway_order_id.ilike(term),
            Order.gateway_payment_id.ilike(term),
        ))
    return [OrderOut(**_out(o)) for o in session.scalars(query)]


@router.get("/orders/{order_id}", response_model=OrderDetail)
def get_order(order_id: uuid.UUID, session: Session = Depends(get_session)):
    return _detail(_get(session, order_id))


@router.post("/orders/{order_id}/cancel", response_model=OrderDetail)
def cancel(order_id: uuid.UUID, session: Session = Depends(get_session)):
    order = _get(session, order_id)
    try:
        cancel_order(session, order)
        session.commit()
    except InvalidTransitionError as e:
        session.rollback()
        raise HTTPException(409, str(e))
    session.refresh(order)
    return _detail(order)
