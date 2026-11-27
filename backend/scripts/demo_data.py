"""Fill a running PayLedger with realistic demo activity (for screenshots / demos).

  make demo      (API must be running: make dev)

Creates ~15 orders and drives them through every path: paid, failed-then-paid,
partial and full refunds, a duplicate webhook delivery, an over-refund attempt
that gets blocked, an abandoned order, and a settlement to the bank.
"""
import random
import secrets

import httpx

from fake_razorpay import DEFAULT_URL, build, rid, send_event

API = DEFAULT_URL.rsplit("/webhooks", 1)[0]
random.seed(7)
PRODUCTS = [149_900, 89_900, 249_900, 54_900, 199_900, 74_900, 129_900, 349_900, 39_900, 99_900]


def create_order(amount: int) -> dict:
    r = httpx.post(f"{API}/orders", json={"external_id": f"PD-{secrets.token_hex(3).upper()}",
                                         "amount_paise": amount})
    r.raise_for_status()
    return r.json()


def pay(order: dict) -> str:
    event = build("payment", order["amount_paise"], None, order["gateway_order_id"])
    send_event(event)
    return event["payload"]["payment"]["entity"]["id"]


def refund(payment_id: str, amount: int) -> dict:
    return send_event(build("refund", amount, payment_id))[0]


def main() -> None:
    httpx.get(f"{API}/health").raise_for_status()
    paid: list[tuple[dict, str]] = []

    for amount in PRODUCTS:                                   # 10 normal paid orders
        o = create_order(amount)
        paid.append((o, pay(o)))

    o = create_order(179_900)                                  # failed, then customer retried
    send_event(build("failed", o["amount_paise"], None, o["gateway_order_id"]))
    paid.append((o, pay(o)))

    o = create_order(64_900)                                   # failed and never retried
    send_event(build("failed", o["amount_paise"], None, o["gateway_order_id"]))

    o = create_order(119_900)                                  # abandoned -> cancelled
    httpx.post(f"{API}/orders/{o['id']}/cancel")

    create_order(84_900)                                       # still waiting for payment

    o = create_order(299_900)                                  # Razorpay delivered the webhook 3 times
    send_event(build("payment", o["amount_paise"], None, o["gateway_order_id"]),
               event_id=rid("evt"), repeat=3)

    (o1, p1), (o2, p2), (o3, p3) = paid[0], paid[1], paid[2]
    refund(p1, 50_000)                                         # partial refund
    refund(p2, o2["amount_paise"])                             # full refund
    refund(p3, 20_000)                                         # partial, then...
    blocked = refund(p3, o3["amount_paise"])                   # ...over-refund: blocked
    print(f"Over-refund attempt -> {blocked['status']} (expected: failed)")

    stats = httpx.get(f"{API}/stats").json()                   # settle most of what Razorpay holds
    settle = int(stats["gateway_held_paise"] * 0.8)
    send_event(build("settlement", settle, None))

    stats = httpx.get(f"{API}/stats").json()
    print(f"Done: {stats['orders_total']} orders, {stats['journal_entries']} journal entries, "
          f"revenue ₹{stats['revenue_paise'] / 100:,.2f}")


if __name__ == "__main__":
    main()
