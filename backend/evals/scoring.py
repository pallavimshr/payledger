"""Score AI reconciliation answers against expected outcomes."""
from collections import defaultdict
from dataclasses import dataclass

from app.models import ReconciliationItem
from app.recon.ai import check_suggestion


@dataclass
class Score:
    name: str
    cause_ok: bool
    guardrails_ok: bool   # suggestion (if any) passed our validation
    entry_ok: bool        # suggestion has the right net effect (or correctly none)
    detail: str

    @property
    def fully_correct(self) -> bool:
        return self.cause_ok and self.guardrails_ok and self.entry_ok


def net_effect(suggestion: dict) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for l in suggestion["lines"]:
        out[l["account_code"]] += l["amount_paise"] if l["direction"] == "debit" else -l["amount_paise"]
    return {k: v for k, v in out.items() if v != 0}


def item_for(facts: dict) -> ReconciliationItem:
    f = facts
    return ReconciliationItem(
        position=0, entity_type=f["entity_type"], entity_id=f["entity_id"], status=f["status"],
        report_amount_paise=f["report_amount_paise"], ledger_amount_paise=f["ledger_amount_paise"],
        report_fee_paise=f["report_fee_paise"], ledger_fee_paise=f["ledger_fee_paise"], report_row=f["report_row"],
    )


def score(case: dict, answer: dict | None, account_codes: set[str]) -> Score:
    if answer is None:
        return Score(case["name"], False, False, False, "no answer")
    cause_ok = answer.get("likely_cause") in case["causes"]
    raw = answer.get("suggested_entry")
    checked = check_suggestion(raw, account_codes, item_for(case["facts"]))
    guardrails_ok = checked.error is None
    expected = [{k: v for k, v in d.items() if v != 0} for d in case["deltas"]]
    if checked.suggestion is None:
        entry_ok = guardrails_ok and (not expected or case["allow_none"])
        got = "none"
    else:
        eff = net_effect(checked.suggestion)
        entry_ok = eff in expected
        got = str(eff)
    detail = f"cause={answer.get('likely_cause')} entry={got}" + (f" REJECTED: {checked.error}" if checked.error else "")
    return Score(case["name"], cause_ok, guardrails_ok, entry_ok, detail)
