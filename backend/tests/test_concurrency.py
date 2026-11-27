"""Race-condition test: two refunds for the same order processed at the same instant.

Without SELECT ... FOR UPDATE both would read "₹1,000 refundable" and both succeed,
refunding ₹1,200 on a ₹1,000 order. With the lock, the second waits, re-reads the
order, sees only ₹400 left, and is rejected.

Only meaningful on Postgres (SQLite has no row locks): run with `make test-pg`.
"""
import threading

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Order
from app.orders import OverRefundError, create_order, on_payment_captured, on_refund_processed
from tests.conftest import TEST_URL

pytestmark = pytest.mark.skipif(TEST_URL.startswith("sqlite"), reason="needs Postgres row locks")


def test_concurrent_refunds_cannot_over_refund(session):
    o = create_order(session, "RACE-1", 100_000)
    session.commit()
    on_payment_captured(session, o.gateway_order_id, "pay_race", 100_000)
    session.commit()

    engine = create_engine(TEST_URL)
    Session = sessionmaker(bind=engine)
    barrier = threading.Barrier(2)
    results: dict[str, str] = {}

    def worker(refund_id: str) -> None:
        with Session() as s:
            barrier.wait()  # start both at the same moment
            try:
                on_refund_processed(s, "pay_race", refund_id, 60_000)
                s.commit()
                results[refund_id] = "ok"
            except OverRefundError:
                s.rollback()
                results[refund_id] = "rejected"

    threads = [threading.Thread(target=worker, args=(rid,)) for rid in ("r1", "r2")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    engine.dispose()

    assert sorted(results.values()) == ["ok", "rejected"]
    session.expire_all()
    order = session.scalars(select(Order).where(Order.external_id == "RACE-1")).one()
    assert order.amount_refunded_paise == 60_000
