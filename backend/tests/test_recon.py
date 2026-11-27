"""Reconciliation: parsing, deterministic matching, AI guardrails (with a fake AI), approvals."""
import csv
import io

import pytest

from app.api import recon as recon_api
from app.recon.report import ReportError, parse_report
from tests.test_webhooks import balances, refund_event, send


# ---------- helpers ----------

def pay(client, pay_id, amount=100_000, fee=2_360):
    send(client, {"event": "payment.captured", "payload": {"payment": {"entity": {
        "id": pay_id, "amount": amount, "currency": "INR", "fee": fee}}}}, event_id=f"evt_{pay_id}")


def csv_bytes(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["entity_id", "type", "amount", "fee", "description"])
    w.writeheader()
    for r in rows:
        w.writerow({"description": "", **r})
    return buf.getvalue().encode()


def upload(client, rows, name="report.csv"):
    r = client.post("/reconciliations", files={"file": (name, csv_bytes(rows), "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()


def by_id(run):
    return {i["entity_id"]: i for i in run["items"]}


class FakeExplainer:
    model = "fake-model"

    def __init__(self, respond):
        self.respond, self.calls = respond, 0

    def explain(self, cases, accounts):
        self.calls += 1
        return [self.respond(c) for c in cases]


@pytest.fixture()
def use_ai(monkeypatch):
    def install(respond):
        fake = FakeExplainer(respond)
        monkeypatch.setattr(recon_api, "get_explainer", lambda: fake)
        return fake
    return install


# ---------- parsing ----------

def test_parse_rupees_to_exact_paise():
    rows = parse_report(b"entity_id,type,amount,fee\npay_1,payment,\"1,499.50\",29.99\n")
    assert rows[0].amount_paise == 149_950 and rows[0].fee_paise == 2_999


def test_parse_handles_excel_bom_and_blank_lines():
    rows = parse_report("﻿entity_id,type,amount,fee\npay_1,payment,10,0\n,,,\n".encode())
    assert len(rows) == 1


@pytest.mark.parametrize("body,msg", [
    (b"entity_id,type,amount\npay_1,payment,10\n", "Missing column"),
    (b"entity_id,type,amount,fee\npay_1,payment,10.005,0\n", "more than 2 decimal"),
    (b"entity_id,type,amount,fee\npay_1,payment,ten,0\n", "not a number"),
    (b"entity_id,type,amount,fee\npay_1,transfer,10,0\n", "unknown type"),
    (b"entity_id,type,amount,fee\npay_1,payment,10,0\npay_1,payment,10,0\n", "duplicate"),
    (b"entity_id,type,amount,fee\n", "no rows"),
])
def test_parse_rejects_bad_reports(body, msg):
    with pytest.raises(ReportError, match=msg):
        parse_report(body)


def test_bad_upload_returns_422(client):
    r = client.post("/reconciliations", files={"file": ("x.csv", b"hello", "text/csv")})
    assert r.status_code == 422


# ---------- matching (no AI) ----------

def test_matcher_classifies_every_case(client):
    pay(client, "pay_ok")
    pay(client, "pay_fee")
    pay(client, "pay_amt")
    pay(client, "pay_pending")
    send(client, refund_event("rfnd_1", 30_000), "evt_r1")
    run = upload(client, [
        {"entity_id": "pay_ok", "type": "payment", "amount": "1000.00", "fee": "23.60"},
        {"entity_id": "pay_fee", "type": "payment", "amount": "1000.00", "fee": "35.40"},
        {"entity_id": "pay_amt", "type": "payment", "amount": "900.00", "fee": "23.60"},
        {"entity_id": "rfnd_1", "type": "refund", "amount": "300.00", "fee": "0"},
        {"entity_id": "pay_ghost", "type": "payment", "amount": "1299.00", "fee": "30.66"},
        {"entity_id": "adj_1", "type": "adjustment", "amount": "-1000.00", "fee": "0"},
    ])
    items = by_id(run)
    assert items["pay_ok"]["status"] == "matched" and items["pay_ok"]["resolution"] == "none"
    assert items["pay_fee"]["status"] == "fee_mismatch"
    assert items["pay_fee"]["ledger_fee_paise"] == 2_360 and items["pay_fee"]["report_fee_paise"] == 3_540
    assert items["pay_amt"]["status"] == "amount_mismatch"
    assert items["rfnd_1"]["status"] == "matched"
    assert items["pay_ghost"]["status"] == "missing_in_ledger"
    assert items["adj_1"]["status"] == "missing_in_ledger"
    assert items["pay_pending"]["status"] == "missing_in_report"
    assert run["open_items"] == 5
    assert all(i["ai"] is None for i in run["items"])  # no key configured -> no AI


def test_previously_matched_entries_are_not_missing_next_time(client):
    pay(client, "pay_1")
    upload(client, [{"entity_id": "pay_1", "type": "payment", "amount": "1000", "fee": "23.60"}])
    pay(client, "pay_2")
    run = upload(client, [{"entity_id": "pay_2", "type": "payment", "amount": "1000", "fee": "23.60"}])
    assert [i["entity_id"] for i in run["items"]] == ["pay_2"]


def test_sample_report_round_trip(client):
    for n in range(6):
        pay(client, f"pay_{n}")
    send(client, refund_event("rfnd_s", 10_000), "evt_rs")
    report = client.get("/reconciliations/sample-report").text
    run = client.post("/reconciliations", files={"file": ("s.csv", report.encode(), "text/csv")}).json()
    statuses = sorted(i["status"] for i in run["items"])
    assert statuses.count("fee_mismatch") == 1
    assert statuses.count("amount_mismatch") == 1
    assert statuses.count("missing_in_ledger") == 2      # missed webhook + chargeback
    assert statuses.count("missing_in_report") == 2      # two newest payments pending


# ---------- AI guardrails ----------

FEE_FIX = {"description": "Extra fee charged by Razorpay", "lines": [
    {"account_code": "expenses:gateway_fees", "direction": "debit", "amount_paise": 1_180},
    {"account_code": "assets:razorpay_clearing", "direction": "credit", "amount_paise": 1_180}]}


def ai_answer(suggestion=FEE_FIX, cause="fee_difference"):
    return lambda c: {"ref": c["ref"], "explanation": f"Explained {c['entity_id']}",
                      "likely_cause": cause, "confidence": "high", "suggested_entry": suggestion}


def fee_mismatch_run(client):
    pay(client, "pay_fee")
    return upload(client, [{"entity_id": "pay_fee", "type": "payment", "amount": "1000.00", "fee": "35.40"}])


def test_valid_ai_suggestion_is_stored(client, use_ai):
    fake = use_ai(ai_answer())
    run = fee_mismatch_run(client)
    ai = by_id(run)["pay_fee"]["ai"]
    assert ai["cause"] == "fee_difference" and ai["suggestion"]["lines"][0]["amount_paise"] == 1_180
    assert ai["error"] is None and run["ai_model"] == "fake-model" and fake.calls == 1


def test_matched_rows_are_never_sent_to_ai(client, use_ai):
    seen = []
    use_ai(lambda c: seen.append(c["entity_id"]) or ai_answer()(c))
    pay(client, "pay_ok")
    upload(client, [{"entity_id": "pay_ok", "type": "payment", "amount": "1000", "fee": "23.60"}])
    assert seen == []


@pytest.mark.parametrize("bad,reason", [
    ({"description": "x", "lines": [
        {"account_code": "expenses:gateway_fees", "direction": "debit", "amount_paise": 1_180},
        {"account_code": "assets:razorpay_clearing", "direction": "credit", "amount_paise": 1_000}]}, "must equal"),
    ({"description": "x", "lines": [
        {"account_code": "expenses:made_up", "direction": "debit", "amount_paise": 100},
        {"account_code": "assets:razorpay_clearing", "direction": "credit", "amount_paise": 100}]}, "unknown account"),
    ({"description": "x", "lines": [
        {"account_code": "expenses:gateway_fees", "direction": "debit", "amount_paise": 99_999_999},
        {"account_code": "assets:razorpay_clearing", "direction": "credit", "amount_paise": 99_999_999}]}, "exceeds"),
    ({"description": "x", "lines": [
        {"account_code": "expenses:gateway_fees", "direction": "debit", "amount_paise": 11.8},
        {"account_code": "assets:razorpay_clearing", "direction": "credit", "amount_paise": 11.8}]}, "integer"),
])
def test_bad_ai_suggestions_are_rejected(client, use_ai, bad, reason):
    use_ai(ai_answer(suggestion=bad))
    ai = by_id(fee_mismatch_run(client))["pay_fee"]["ai"]
    assert ai["suggestion"] is None and reason in ai["error"]
    assert ai["explanation"]  # the explanation is still useful to a human


def test_ai_failure_is_recorded_not_raised(client, use_ai):
    def boom(c):
        raise RuntimeError("quota exceeded")
    use_ai(boom)
    ai = by_id(fee_mismatch_run(client))["pay_fee"]["ai"]
    assert "quota exceeded" in ai["error"]


def test_invented_refs_are_ignored(client, use_ai):
    use_ai(lambda c: {"ref": "999", "explanation": "?", "likely_cause": "other", "confidence": "low"})
    ai = by_id(fee_mismatch_run(client))["pay_fee"]["ai"]
    assert ai["error"] == "AI returned no result for this row"


def test_unknown_cause_is_coerced_to_other(client, use_ai):
    use_ai(ai_answer(cause="aliens"))
    assert by_id(fee_mismatch_run(client))["pay_fee"]["ai"]["cause"] == "other"


# ---------- human approval ----------

def test_accept_posts_correction_once(client, use_ai):
    use_ai(ai_answer())
    item = by_id(fee_mismatch_run(client))["pay_fee"]
    before = balances(client)["expenses:gateway_fees"]
    r = client.post(f"/reconciliation-items/{item['id']}/accept")
    assert r.status_code == 200 and r.json()["resolution"] == "accepted"
    assert balances(client)["expenses:gateway_fees"] == before + 1_180
    assert client.post(f"/reconciliation-items/{item['id']}/accept").status_code == 409


def test_accept_without_suggestion_is_400(client):
    item = by_id(fee_mismatch_run(client))["pay_fee"]
    assert client.post(f"/reconciliation-items/{item['id']}/accept").status_code == 400


def test_dismiss(client):
    item = by_id(fee_mismatch_run(client))["pay_fee"]
    r = client.post(f"/reconciliation-items/{item['id']}/dismiss")
    assert r.json()["resolution"] == "dismissed"
    assert client.post(f"/reconciliation-items/{item['id']}/dismiss").status_code == 409


def test_explain_endpoint_needs_key(client):
    run = fee_mismatch_run(client)
    assert client.post(f"/reconciliations/{run['id']}/explain").status_code == 400
