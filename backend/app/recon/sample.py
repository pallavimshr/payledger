"""Build a realistic settlement report from the current ledger, with planted problems.

Used for demos (`make demo-report` or the dashboard's "Download sample report").
"""
import csv
import io
import secrets
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.recon.matcher import ledger_facts, razorpay_entries, sort_key

COLUMNS = ["entity_id", "type", "amount", "fee", "tax", "currency", "order_id",
           "settlement_id", "settled_at", "description"]


def rupees(paise: int) -> str:
    sign = "-" if paise < 0 else ""
    return f"{sign}{abs(paise) // 100}.{abs(paise) % 100:02d}"


def build_sample_report(session: Session) -> str:
    entries = sorted(razorpay_entries(session).items(), key=lambda kv: sort_key(kv[1].created_at))
    payments = [(k, e) for k, e in entries if k.startswith("razorpay:payment:")]
    refunds = [(k, e) for k, e in entries if k.startswith("razorpay:refund:")]
    setl = f"setl_{secrets.token_hex(7)}"
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    out: list[dict] = []

    def row(entity_id, kind, amount, fee, desc=""):
        tax = round(fee * 18 / 118) if fee > 0 else 0
        out.append({"entity_id": entity_id, "type": kind, "amount": rupees(amount), "fee": rupees(fee),
                    "tax": rupees(tax), "currency": "INR", "order_id": "", "settlement_id": setl,
                    "settled_at": today, "description": desc})

    # The two most recent payments are left out: captured but not settled yet.
    settled = payments[:-2] if len(payments) > 2 else payments
    for n, (key, entry) in enumerate(settled):
        f = ledger_facts(entry)
        pay_id = key.split(":", 2)[2]
        if n == 1:   # international card: Razorpay charged 3% + GST instead of 2% + GST
            row(pay_id, "payment", f.amount_paise, round(f.amount_paise * 0.03 * 1.18), "International card")
        elif n == 3:  # amount differs: report shows ₹100 less than we booked
            row(pay_id, "payment", f.amount_paise - 10_000, f.fee_paise)
        else:
            row(pay_id, "payment", f.amount_paise, f.fee_paise)
    for key, entry in refunds:
        row(key.split(":", 2)[2], "refund", ledger_facts(entry).amount_paise, 0)

    # A payment Razorpay processed whose webhook never reached us.
    row(f"pay_{secrets.token_hex(7)}", "payment", 129_900, round(129_900 * 0.02 * 1.18))
    # A chargeback: customer disputed a payment, Razorpay deducted it from the settlement.
    disputed = settled[0][0].split(":", 2)[2] if settled else "pay_unknown"
    row(f"adj_{secrets.token_hex(7)}", "adjustment", -ledger_facts(settled[0][1]).amount_paise if settled else -50_000,
        0, f"Chargeback for {disputed} (reason: product not received)")

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS)
    w.writeheader()
    w.writerows(out)
    return buf.getvalue()
