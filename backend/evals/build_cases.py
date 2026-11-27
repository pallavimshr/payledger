"""Generates evals/recon_cases.json (run once; the JSON is committed so results are comparable).

Each case = the facts the AI sees + what a correct answer looks like:
  causes:  acceptable likely_cause values
  deltas:  acceptable net effects of the suggested entry, per account
           (+ = debit, - = credit, paise). [] means "no entry is the right answer".
  allow_none: a null suggestion is also acceptable (ambiguous cases needing a human)
"""
import json
from pathlib import Path

CL, FEE, SALES = "assets:razorpay_clearing", "expenses:gateway_fees", "revenue:sales"
cases = []


def add(name, facts, causes, deltas, allow_none=False):
    cases.append({"name": name, "facts": facts, "causes": causes, "deltas": deltas, "allow_none": allow_none})


def fee(amount, pct):
    return round(amount * pct * 1.18)


# 1. Fee mismatches (6): international cards, EMI, and one fee LOWER than booked
for i, (amt, booked, charged, note) in enumerate([
    (100_000, 0.02, 0.03, "International card"), (249_900, 0.02, 0.03, "International card"),
    (54_900, 0.02, 0.03, ""), (1_99_900, 0.02, 0.025, "EMI"), (89_900, 0.02, 0.0236, "Amex"),
    (149_900, 0.02, 0.0, "Fee waived: promotional zero-MDR UPI")]):
    b, c = fee(amt, booked), fee(amt, charged)
    add(f"fee_{i}", {"status": "fee_mismatch", "entity_type": "payment", "entity_id": f"pay_fee{i}",
        "report_amount_paise": amt, "ledger_amount_paise": amt, "report_fee_paise": c, "ledger_fee_paise": b,
        "report_row": {"description": note}},
        ["fee_difference"], [{FEE: c - b, CL: b - c}])

# 2. Payments missing in ledger (5): webhook never arrived
for i, amt in enumerate([129_900, 49_900, 3_49_900, 19_900, 79_900]):
    f = fee(amt, 0.02)
    add(f"missed_pay_{i}", {"status": "missing_in_ledger", "entity_type": "payment", "entity_id": f"pay_miss{i}",
        "report_amount_paise": amt, "ledger_amount_paise": None, "report_fee_paise": f, "ledger_fee_paise": None,
        "report_row": {"description": ""}},
        ["webhook_missed"], [{CL: amt - f, FEE: f, SALES: -amt}])

# 3. Refunds missing in ledger (3)
for i, amt in enumerate([30_000, 1_49_900, 5_000]):
    add(f"missed_refund_{i}", {"status": "missing_in_ledger", "entity_type": "refund", "entity_id": f"rfnd_miss{i}",
        "report_amount_paise": amt, "ledger_amount_paise": None, "report_fee_paise": 0, "ledger_fee_paise": None,
        "report_row": {"description": ""}},
        ["webhook_missed"], [{SALES: amt, CL: -amt}])

# 4. Chargebacks (4): negative adjustment, deducted from what Razorpay holds
for i, (amt, reason) in enumerate([(99_900, "product not received"), (2_49_900, "fraudulent transaction"),
                                   (54_900, "duplicate charge claimed by customer"), (14_900, "item not as described")]):
    add(f"chargeback_{i}", {"status": "missing_in_ledger", "entity_type": "adjustment", "entity_id": f"adj_cb{i}",
        "report_amount_paise": -amt, "ledger_amount_paise": None, "report_fee_paise": 0, "ledger_fee_paise": None,
        "report_row": {"description": f"Chargeback for pay_x{i} (reason: {reason})"}},
        ["chargeback"], [{SALES: amt, CL: -amt}])

# 5. Other adjustments (2): Razorpay credits money back
for i, (amt, desc) in enumerate([(2_360, "Fee reversal for refunded payment pay_r1"),
                                 (5_900, "GST credit adjustment on gateway fees")]):
    add(f"credit_adj_{i}", {"status": "missing_in_ledger", "entity_type": "adjustment", "entity_id": f"adj_cr{i}",
        "report_amount_paise": amt, "ledger_amount_paise": None, "report_fee_paise": 0, "ledger_fee_paise": None,
        "report_row": {"description": desc}},
        ["other_adjustment", "fee_difference"], [{CL: amt, FEE: -amt}])

# 6. Recent payments not in report yet (4): normal T+2 timing, no entry needed
for i, amt in enumerate([1_79_900, 29_900, 99_900, 64_900]):
    f = fee(amt, 0.02)
    add(f"pending_{i}", {"status": "missing_in_report", "entity_type": "payment", "entity_id": f"pay_new{i}",
        "report_amount_paise": None, "ledger_amount_paise": amt, "report_fee_paise": None, "ledger_fee_paise": f,
        "report_row": None},
        ["pending_settlement"], [])

# 7. Amount mismatches (4): ambiguous, a human must check; fixing to the report's figure is also fine
for i, (ledger, report) in enumerate([(54_900, 44_900), (1_00_000, 90_000), (2_99_900, 2_99_000), (49_900, 59_900)]):
    f = fee(ledger, 0.02)
    d = ledger - report
    add(f"amount_{i}", {"status": "amount_mismatch", "entity_type": "payment", "entity_id": f"pay_amt{i}",
        "report_amount_paise": report, "ledger_amount_paise": ledger, "report_fee_paise": f, "ledger_fee_paise": f,
        "report_row": {"description": ""}},
        ["amount_error", "data_error"], [{SALES: d, CL: -d}], allow_none=True)

# 8. Data errors (2): junk rows; no entry should be posted
add("data_zero", {"status": "missing_in_ledger", "entity_type": "payment", "entity_id": "pay_test0",
    "report_amount_paise": 0, "ledger_amount_paise": None, "report_fee_paise": 0, "ledger_fee_paise": None,
    "report_row": {"description": "Test transaction"}}, ["data_error", "other"], [])
add("data_pending_refund", {"status": "missing_in_report", "entity_type": "refund", "entity_id": "rfnd_new0",
    "report_amount_paise": None, "ledger_amount_paise": 20_000, "report_fee_paise": None, "ledger_fee_paise": None,
    "report_row": None}, ["pending_settlement"], [])

Path(__file__).with_name("recon_cases.json").write_text(json.dumps(cases, indent=1))
print(f"Wrote {len(cases)} cases")
