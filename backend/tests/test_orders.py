"""Order state machine + how webhooks drive it."""
import pytest

from app.models import OrderStatus as S
from app.orders import ALLOWED, InvalidTransitionError, transition
from tests.test_webhooks import balances, send


# ---------- helpers ----------

def new_order(client, ext="ORD-1", amount=100_000):
    r = client.post("/orders", json={"external_id": ext, "amount_paise": amount})
    assert r.status_code == 201, r.text
    return r.json()


def order(client, o):
    return client.get(f"/orders/{o['id']}").json()


def pay(client, o, pay_id="pay_1", amount=None, event_id=None):
    return send(client, {"event": "payment.captured", "payload": {"payment": {"entity": {
        "id": pay_id, "amount": amount or o["amount_paise"], "currency": "INR", "fee": 2_360,
        "order_id": o["gateway_order_id"]}}}}, event_id=event_id or f"evt_{pay_id}")


def fail(client, o, pay_id="pay_f", event_id=None):
    return send(client, {"event": "payment.failed", "payload": {"payment": {"entity": {
        "id": pay_id, "amount": o["amount_paise"], "currency": "INR",
        "order_id": o["gateway_order_id"], "error_description": "Card declined"}}}},
        event_id=event_id or f"evt_{pay_id}")


def refund(client, rfnd_id, amount, pay_id="pay_1"):
    return send(client, {"event": "refund.processed", "payload": {"refund": {"entity": {
        "id": rfnd_id, "amount": amount, "currency": "INR", "payment_id": pay_id}}}},
        event_id=f"evt_{rfnd_id}")


# ---------- state machine rules ----------

def test_terminal_states_allow_nothing():
    assert ALLOWED[S.REFUNDED] == set() and ALLOWED[S.CANCELLED] == set()


@pytest.mark.parametrize("start,target", [
    (S.CREATED, S.REFUNDED),            # can't refund an unpaid order
    (S.CREATED, S.PARTIALLY_REFUNDED),
    (S.PAID, S.CANCELLED),              # can't cancel after money was taken
    (S.PAID, S.FAILED),                 # a paid order can't become failed
    (S.REFUNDED, S.PAID),
    (S.CANCELLED, S.PAID),
])
def test_invalid_transitions_raise(session, start, target):
    from app.orders import create_order
    o = create_order(session, f"X-{start}-{target}", 100)
    o.status = start.value
    with pytest.raises(InvalidTransitionError):
        transition(session, o, target, "test")


# ---------- API + webhook flows ----------

def test_create_order(client):
    o = new_order(client)
    assert o["status"] == "created" and o["refundable_paise"] == 100_000
    assert o["gateway_order_id"].startswith("order_")
    assert [h["to_status"] for h in o["history"]] == ["created"]


def test_duplicate_external_id_409(client):
    new_order(client, "ORD-1")
    assert client.post("/orders", json={"external_id": "ORD-1", "amount_paise": 5}).status_code == 409


def test_payment_marks_order_paid_and_posts_ledger(client):
    o = new_order(client)
    assert pay(client, o).json()["status"] == "processed"
    d = order(client, o)
    assert d["status"] == "paid" and d["gateway_payment_id"] == "pay_1"
    assert balances(client)["revenue:sales"] == 100_000


def test_same_payment_twice_under_new_event_id_is_noop(client):
    o = new_order(client)
    pay(client, o, event_id="evt_a")
    pay(client, o, event_id="evt_b")
    d = order(client, o)
    assert d["status"] == "paid" and len(d["history"]) == 2   # created, paid
    assert balances(client)["revenue:sales"] == 100_000


def test_second_different_payment_is_flagged_not_lost(client):
    o = new_order(client)
    pay(client, o, pay_id="pay_1")
    pay(client, o, pay_id="pay_2")   # customer was charged twice
    d = order(client, o)
    assert d["status"] == "paid"
    assert "refund needed" in d["history"][-1]["note"]
    assert balances(client)["revenue:sales"] == 200_000   # ledger reflects reality: we got paid twice


def test_failed_then_successful_retry(client):
    o = new_order(client)
    fail(client, o)
    assert order(client, o)["status"] == "failed"
    pay(client, o)
    assert [h["to_status"] for h in order(client, o)["history"]] == ["created", "failed", "paid"]


def test_late_failure_does_not_unpay(client):
    o = new_order(client)
    pay(client, o)
    fail(client, o, pay_id="pay_old")   # failure of an older attempt arrives late
    assert order(client, o)["status"] == "paid"


def test_partial_then_full_refund(client):
    o = new_order(client)
    pay(client, o)
    refund(client, "rfnd_1", 30_000)
    d = order(client, o)
    assert d["status"] == "partially_refunded" and d["refundable_paise"] == 70_000
    refund(client, "rfnd_2", 70_000)
    d = order(client, o)
    assert d["status"] == "refunded" and d["refundable_paise"] == 0
    assert len(d["refunds"]) == 2
    assert balances(client)["revenue:sales"] == 0


def test_over_refund_fails_and_writes_nothing(client):
    o = new_order(client)
    pay(client, o)
    refund(client, "rfnd_1", 60_000)
    r = refund(client, "rfnd_2", 50_000)     # only 40,000 left
    assert r.json()["status"] == "failed"
    d = order(client, o)
    assert d["status"] == "partially_refunded" and d["amount_refunded_paise"] == 60_000
    assert balances(client)["revenue:sales"] == 40_000   # the ledger entry was rolled back too
    ev = [e for e in client.get("/webhook-events").json() if e["event_id"] == "evt_rfnd_2"][0]
    assert "OverRefundError" in ev["last_error"]


def test_refund_for_untracked_payment_still_posts_ledger(client):
    send(client, {"event": "payment.captured", "payload": {"payment": {"entity": {
        "id": "pay_x", "amount": 50_000, "currency": "INR", "fee": 0}}}}, event_id="e1")
    refund(client, "rfnd_x", 10_000, pay_id="pay_x")
    assert balances(client)["revenue:sales"] == 40_000


def test_cancel_created_order(client):
    o = new_order(client)
    r = client.post(f"/orders/{o['id']}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"


def test_cannot_cancel_paid_order(client):
    o = new_order(client)
    pay(client, o)
    assert client.post(f"/orders/{o['id']}/cancel").status_code == 409


def test_payment_on_cancelled_order_fails_safely(client):
    o = new_order(client)
    client.post(f"/orders/{o['id']}/cancel")
    assert pay(client, o).json()["status"] == "failed"
    assert balances(client)["revenue:sales"] == 0


def test_list_orders_filter_by_status(client):
    a, b = new_order(client, "A"), new_order(client, "B")
    pay(client, a)
    assert [o["external_id"] for o in client.get("/orders?status=paid").json()] == ["A"]


def test_search_orders_by_number_and_payment_id(client):
    a, b = new_order(client, "PD-ALPHA"), new_order(client, "PD-BETA")
    pay(client, b, pay_id="pay_findme")
    assert [o["external_id"] for o in client.get("/orders?q=alpha").json()] == ["PD-ALPHA"]
    assert [o["external_id"] for o in client.get("/orders?q=findme").json()] == ["PD-BETA"]
    assert len(client.get("/orders?q=").json()) == 2
