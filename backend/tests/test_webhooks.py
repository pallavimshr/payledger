"""Webhook guarantees: authenticity, exactly-once effects, crash recovery."""
import hashlib
import hmac
import json

from app.config import settings
from app.models import WebhookEvent
from app.webhooks import razorpay
from app.webhooks.inbox import process_pending


def payment_event(pay_id="pay_A", amount=100_000, fee=2_360):
    return {"event": "payment.captured", "payload": {"payment": {"entity": {
        "id": pay_id, "amount": amount, "currency": "INR", "fee": fee, "order_id": "order_1"}}}}


def refund_event(rfnd_id="rfnd_A", amount=30_000):
    return {"event": "refund.processed", "payload": {"refund": {"entity": {
        "id": rfnd_id, "amount": amount, "currency": "INR", "payment_id": "pay_A"}}}}


def settlement_event(setl_id="setl_A", amount=67_640):
    return {"event": "settlement.processed", "payload": {"settlement": {"entity": {
        "id": setl_id, "amount": amount, "utr": "UTR1"}}}}


def send(client, event, event_id="evt_1", secret=None):
    body = json.dumps(event).encode()
    sig = hmac.new((secret or settings.razorpay_webhook_secret).encode(), body, hashlib.sha256).hexdigest()
    return client.post("/webhooks/razorpay", content=body, headers={
        "Content-Type": "application/json", "X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": event_id})


def balances(client):
    return {a["code"]: a["balance_paise"] for a in client.get("/accounts").json()}


def assert_books_balance(client):
    """Sum of debit-normal balances == sum of credit-normal balances."""
    accts = client.get("/accounts").json()
    debit_side = sum(a["balance_paise"] for a in accts if a["type"] in ("asset", "expense"))
    credit_side = sum(a["balance_paise"] for a in accts if a["type"] not in ("asset", "expense"))
    assert debit_side == credit_side


def test_payment_captured_posts_entry(client):
    r = send(client, payment_event())
    assert r.status_code == 200 and r.json()["status"] == "processed"
    b = balances(client)
    assert b["revenue:sales"] == 100_000
    assert b["assets:razorpay_clearing"] == 97_640
    assert b["expenses:gateway_fees"] == 2_360
    assert_books_balance(client)


def test_invalid_signature_rejected_and_nothing_stored(client):
    r = send(client, payment_event(), secret="wrong_secret")
    assert r.status_code == 400
    assert client.get("/webhook-events").json() == []
    assert balances(client)["revenue:sales"] == 0


def test_tampered_body_rejected(client):
    body = json.dumps(payment_event()).encode()
    sig = hmac.new(settings.razorpay_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    tampered = body.replace(b"100000", b"999999")
    r = client.post("/webhooks/razorpay", content=tampered,
                    headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": "evt_x"})
    assert r.status_code == 400


def test_same_event_delivered_three_times_counts_once(client):
    statuses = [send(client, payment_event(), event_id="evt_dup").json()["status"] for _ in range(3)]
    assert statuses == ["processed", "duplicate", "duplicate"]
    assert balances(client)["revenue:sales"] == 100_000


def test_same_payment_under_different_event_ids_counts_once(client):
    send(client, payment_event(), event_id="evt_1")
    send(client, payment_event(), event_id="evt_2")
    assert balances(client)["revenue:sales"] == 100_000
    assert len(client.get("/journal-entries").json()) == 1


def test_full_lifecycle_payment_refund_settlement(client):
    send(client, payment_event(), "evt_1")            # +1000 sale, 23.60 fee
    send(client, refund_event(amount=30_000), "evt_2")  # 300 refunded
    send(client, settlement_event(amount=67_640), "evt_3")  # rest paid to bank
    b = balances(client)
    assert b["revenue:sales"] == 70_000
    assert b["assets:razorpay_clearing"] == 0        # fully settled
    assert b["assets:bank"] == 67_640
    assert b["expenses:gateway_fees"] == 2_360
    assert_books_balance(client)


def test_unhandled_event_type_is_ignored(client):
    r = send(client, {"event": "payment.authorized", "payload": {}})
    assert r.json()["status"] == "ignored"


def test_failed_processing_is_retried_by_worker(client, session, monkeypatch):
    # Simulate a bug/outage: the handler crashes on the first attempt.
    real = razorpay.HANDLERS["payment.captured"]
    calls = {"n": 0}

    def flaky(event):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("database hiccup")
        return real(event)

    monkeypatch.setitem(razorpay.HANDLERS, "payment.captured", flaky)

    r = send(client, payment_event())
    assert r.status_code == 200 and r.json()["status"] == "failed"
    assert balances(client)["revenue:sales"] == 0      # nothing half-written

    assert process_pending(session) == {"processed": 1}
    assert balances(client)["revenue:sales"] == 100_000
    event = session.query(WebhookEvent).one()
    assert event.attempts == 2 and event.last_error is None


def test_unbalanced_handler_output_fails_safely(client, monkeypatch):
    # If a handler ever produced bad lines, validate_entry blocks it.
    from app.ledger import PostingLine
    from app.models import Direction
    from app.webhooks.razorpay import EntrySpec

    monkeypatch.setitem(razorpay.HANDLERS, "payment.captured", lambda e: EntrySpec(
        "bad", "k1", [PostingLine("assets:bank", Direction.DEBIT, 5),
                      PostingLine("revenue:sales", Direction.CREDIT, 4)]))
    r = send(client, payment_event())
    assert r.json()["status"] == "failed"
    assert client.get("/journal-entries").json() == []
