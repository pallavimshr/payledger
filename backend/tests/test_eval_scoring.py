"""The eval scorer itself must be right, or the accuracy numbers mean nothing."""
import json
from pathlib import Path

from evals.run_eval import run
from evals.scoring import score

CASES = json.loads((Path(__file__).parents[1] / "evals" / "recon_cases.json").read_text())
CODES = {"assets:bank", "assets:razorpay_clearing", "assets:stripe_clearing", "liabilities:refunds_payable",
         "equity:owner", "revenue:sales", "expenses:gateway_fees"}


def perfect_answer(case):
    entry = None
    if case["deltas"]:
        lines = [{"account_code": a, "direction": "debit" if v > 0 else "credit", "amount_paise": abs(v)}
                 for a, v in case["deltas"][0].items() if v]
        entry = {"description": "fix", "lines": lines}
    return {"likely_cause": case["causes"][0], "confidence": "high", "explanation": "x", "suggested_entry": entry}


class Perfect:
    model = "perfect"

    def explain(self, facts, accounts):
        by_id = {c["facts"]["entity_id"]: c for c in CASES}
        return [{"ref": f["ref"], **perfect_answer(by_id[f["entity_id"]])} for f in facts]


def test_case_set_is_sizeable_and_unique():
    assert len(CASES) >= 30
    assert len({c["name"] for c in CASES}) == len(CASES)


def test_perfect_model_scores_100_percent():
    assert all(s.fully_correct for s in run(Perfect(), CASES))


def test_wrong_cause_and_wrong_entry_are_caught():
    case = next(c for c in CASES if c["name"] == "fee_0")
    bad = perfect_answer(case) | {"likely_cause": "chargeback"}
    assert not score(case, bad, CODES).cause_ok
    flipped = perfect_answer(case)
    for l in flipped["suggested_entry"]["lines"]:
        l["direction"] = "credit" if l["direction"] == "debit" else "debit"
    assert not score(case, flipped, CODES).entry_ok


def test_entry_where_none_is_expected_is_wrong():
    case = next(c for c in CASES if c["name"] == "pending_0")
    ans = perfect_answer(case) | {"suggested_entry": {"description": "x", "lines": [
        {"account_code": "assets:bank", "direction": "debit", "amount_paise": 100},
        {"account_code": "assets:razorpay_clearing", "direction": "credit", "amount_paise": 100}]}}
    assert not score(case, ans, CODES).entry_ok


def test_missing_answer_scores_zero():
    assert not score(CASES[0], None, CODES).fully_correct
