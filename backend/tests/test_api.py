"""End-to-end tests through the HTTP API."""


def sale(amount=100_000, fee=2_000, key=None):
    body = {
        "description": "Order #1001 paid via Razorpay",
        "lines": [
            {"account_code": "assets:razorpay_clearing", "direction": "debit", "amount_paise": amount - fee},
            {"account_code": "expenses:gateway_fees", "direction": "debit", "amount_paise": fee},
            {"account_code": "revenue:sales", "direction": "credit", "amount_paise": amount},
        ],
    }
    if key:
        body["idempotency_key"] = key
    return body


def balances(client):
    return {a["code"]: a["balance_paise"] for a in client.get("/accounts").json()}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_seeded_accounts_start_at_zero(client):
    b = balances(client)
    assert b["revenue:sales"] == 0 and len(b) == 7


def test_post_sale_updates_balances(client):
    r = client.post("/journal-entries", json=sale())
    assert r.status_code == 201, r.text
    b = balances(client)
    assert b["assets:razorpay_clearing"] == 98_000
    assert b["expenses:gateway_fees"] == 2_000
    assert b["revenue:sales"] == 100_000


def test_unbalanced_entry_returns_422_and_writes_nothing(client):
    body = sale()
    body["lines"][2]["amount_paise"] = 99_999
    r = client.post("/journal-entries", json=body)
    assert r.status_code == 422
    assert client.get("/journal-entries").json() == []


def test_unknown_account_returns_422(client):
    body = sale()
    body["lines"][0]["account_code"] = "assets:does_not_exist"
    assert client.post("/journal-entries", json=body).status_code == 422


def test_same_idempotency_key_cannot_post_twice(client):
    assert client.post("/journal-entries", json=sale(key="pay_ABC")).status_code == 201
    assert client.post("/journal-entries", json=sale(key="pay_ABC")).status_code == 409
    assert balances(client)["revenue:sales"] == 100_000  # counted once, not twice


def test_create_duplicate_account_returns_409(client):
    body = {"code": "assets:bank", "name": "Dup", "type": "asset"}
    assert client.post("/accounts", json=body).status_code == 409
