"""Send a realistic, correctly signed Razorpay webhook to your local API.

Lets you test without a Razorpay account. Examples (from backend/):
  uv run python scripts/fake_razorpay.py payment --amount 1000
  uv run python scripts/fake_razorpay.py refund  --amount 300 --payment pay_xxx
  uv run python scripts/fake_razorpay.py settlement --amount 697.64
  uv run python scripts/fake_razorpay.py payment --amount 1000 --repeat 3   # duplicate deliveries
"""
import argparse
import hashlib
import hmac
import json
import secrets
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make "app" importable
from app.config import settings  # noqa: E402


def rid(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(7)}"


def build(kind: str, paise: int, payment_id: str | None) -> dict:
    now = int(time.time())
    if kind == "payment":
        fee = round(paise * 0.02 * 1.18)  # 2% fee + 18% GST, like Razorpay's standard plan
        entity = {"id": rid("pay"), "entity": "payment", "amount": paise, "currency": "INR",
                  "status": "captured", "order_id": rid("order"), "method": "upi",
                  "fee": fee, "tax": fee - round(paise * 0.02), "created_at": now}
        return {"event": "payment.captured", "contains": ["payment"],
                "payload": {"payment": {"entity": entity}}, "created_at": now}
    if kind == "refund":
        entity = {"id": rid("rfnd"), "entity": "refund", "amount": paise, "currency": "INR",
                  "payment_id": payment_id or rid("pay"), "status": "processed", "created_at": now}
        return {"event": "refund.processed", "contains": ["refund"],
                "payload": {"refund": {"entity": entity}}, "created_at": now}
    entity = {"id": rid("setl"), "entity": "settlement", "amount": paise, "status": "processed",
              "fees": 0, "tax": 0, "utr": secrets.token_hex(6).upper(), "created_at": now}
    return {"event": "settlement.processed", "contains": ["settlement"],
            "payload": {"settlement": {"entity": entity}}, "created_at": now}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["payment", "refund", "settlement"])
    ap.add_argument("--amount", type=float, required=True, help="in rupees, e.g. 1000 or 697.64")
    ap.add_argument("--payment", help="payment id (for refunds)")
    ap.add_argument("--repeat", type=int, default=1, help="send the same event N times")
    ap.add_argument("--url", default="http://localhost:8000/webhooks/razorpay")
    args = ap.parse_args()

    body = json.dumps(build(args.kind, round(args.amount * 100), args.payment)).encode()
    signature = hmac.new(settings.razorpay_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {"Content-Type": "application/json", "X-Razorpay-Signature": signature,
               "X-Razorpay-Event-Id": rid("evt")}
    for i in range(args.repeat):
        r = httpx.post(args.url, content=body, headers=headers)
        print(f"#{i + 1}: {r.status_code} {r.json()}")


if __name__ == "__main__":
    main()
