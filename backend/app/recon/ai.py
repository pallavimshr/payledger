"""AI explanations for reconciliation mismatches.

Design rules (the interview story):
  1. The AI never decides WHAT is wrong; the deterministic matcher already did.
     The AI explains WHY and proposes a fix.
  2. Output is forced into a JSON schema (structured output), not free text.
  3. Every suggested journal entry is re-validated by our own code: known accounts,
     integer paise, debits == credits, sane size. Invalid suggestions are dropped.
  4. Nothing is posted automatically. A person clicks "Accept".
"""
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ledger import LedgerError, PostingLine, validate_entry
from app.models import Account, Direction, ReconciliationItem, ReconStatus

CAUSES = [
    "webhook_missed",          # gateway processed it, our system never recorded it
    "fee_difference",          # different fee rate/GST than we booked (e.g. international card)
    "amount_error",            # wrong amount recorded on one side
    "chargeback",              # customer disputed; gateway debited us
    "other_adjustment",        # other gateway deduction/credit
    "pending_settlement",      # normal timing: will appear in a later report
    "data_error",              # duplicate, typo or corrupt row
    "other",
]

SYSTEM_PROMPT = """You are a payments reconciliation analyst for an Indian e-commerce business that \
uses Razorpay. You receive discrepancies found by comparing Razorpay's settlement report with the \
business's double-entry ledger. For each one: explain the most likely cause in 1-3 plain sentences \
a finance person understands, classify it, rate your confidence, and propose ONE correcting journal \
entry that would make the ledger reflect reality, or null if the ledger needs no change.

Ledger conventions (amounts are integer paise; 100 paise = Rs 1):
- payment captured: debit assets:razorpay_clearing (amount - fee), debit expenses:gateway_fees (fee), credit revenue:sales (amount)
- refund: debit revenue:sales, credit assets:razorpay_clearing
- Razorpay fees already include 18% GST. Settlements usually arrive T+2 days, so a recent payment
  missing from the report is normally just pending.
- Adjustment rows with a negative amount are deductions by Razorpay (e.g. chargebacks).

Hard rules for suggested entries: use ONLY account codes from the provided chart of accounts; \
amounts are positive integers in paise; total debits must equal total credits; the entry must only \
correct the difference, never re-book what is already correct. Never invent payment IDs."""

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "results": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "ref": {"type": "STRING"},
                    "explanation": {"type": "STRING"},
                    "likely_cause": {"type": "STRING", "enum": CAUSES},
                    "confidence": {"type": "STRING", "enum": ["low", "medium", "high"]},
                    "suggested_entry": {
                        "type": "OBJECT",
                        "nullable": True,
                        "properties": {
                            "description": {"type": "STRING"},
                            "lines": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "account_code": {"type": "STRING"},
                                        "direction": {"type": "STRING", "enum": ["debit", "credit"]},
                                        "amount_paise": {"type": "INTEGER"},
                                    },
                                    "required": ["account_code", "direction", "amount_paise"],
                                },
                            },
                        },
                        "required": ["description", "lines"],
                    },
                },
                "required": ["ref", "explanation", "likely_cause", "confidence"],
            },
        }
    },
    "required": ["results"],
}


class Explainer(Protocol):
    model: str

    def explain(self, cases: list[dict], accounts: list[dict]) -> list[dict]: ...


class AIError(RuntimeError):
    pass


class GeminiExplainer:
    """Calls the Gemini REST API with a JSON response schema."""

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str, model: str, timeout: float = 120.0):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def _thinking_config(self) -> dict | None:
        """Ask for light reasoning: this task is narrow, and heavy thinking only adds latency."""
        if self.model.startswith("gemini-2.5-flash"):
            return {"thinkingBudget": 0}
        if self.model.startswith("gemini-3"):
            return {"thinkingLevel": "low"}
        return None

    def explain(self, cases: list[dict], accounts: list[dict]) -> list[dict]:
        body = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": json.dumps(
                {"chart_of_accounts": accounts, "discrepancies": cases}, indent=1)}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": RESPONSE_SCHEMA,
            },
        }
        thinking = self._thinking_config()
        if thinking:
            body["generationConfig"]["thinkingConfig"] = thinking
        for attempt in range(4):
            try:
                r = httpx.post(self.URL.format(model=self.model), json=body, timeout=self.timeout,
                               headers={"x-goog-api-key": self.api_key})
            except httpx.HTTPError as e:
                raise AIError(f"Could not reach Gemini: {e}") from e
            if r.status_code == 400 and "thinking" in r.text.lower() and "thinkingConfig" in body["generationConfig"]:
                del body["generationConfig"]["thinkingConfig"]  # model doesn't support it: retry without
                continue
            if r.status_code in (429, 503) and attempt < 3:
                time.sleep(5 * 2**attempt)  # free tier rate limit / overload: back off and retry
                continue
            if r.status_code != 200:
                raise AIError(f"Gemini API {r.status_code}: {r.text[:300]}")
            break
        try:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)["results"]
        except (KeyError, IndexError, ValueError) as e:
            raise AIError(f"Unexpected Gemini response: {e}") from e


def get_explainer() -> Explainer | None:
    from app.config import settings
    if not settings.gemini_api_key:
        return None
    return GeminiExplainer(settings.gemini_api_key, settings.gemini_model)


# ---------------------------------------------------------------------------
# Guardrails: never trust model output.
# ---------------------------------------------------------------------------

@dataclass
class Checked:
    suggestion: dict | None
    error: str | None


def check_suggestion(raw: dict | None, account_codes: set[str], item: ReconciliationItem) -> Checked:
    if not raw:
        return Checked(None, None)
    try:
        lines = [
            PostingLine(l["account_code"], Direction(l["direction"]), l["amount_paise"])
            for l in raw.get("lines", [])
        ]
        validate_entry(lines)
    except (KeyError, ValueError, TypeError, LedgerError) as e:
        return Checked(None, f"AI suggestion rejected: {e}")
    unknown = {l.account_code for l in lines} - account_codes
    if unknown:
        return Checked(None, f"AI suggestion rejected: unknown account(s) {', '.join(sorted(unknown))}")
    # Sanity cap: a correction can't be bigger than the money involved in this row.
    known = [abs(v) for v in (item.report_amount_paise, item.ledger_amount_paise) if v is not None]
    cap = max(known) if known else 0
    total = sum(l.amount_paise for l in lines if l.direction == Direction.DEBIT)
    if total > cap:
        return Checked(None, f"AI suggestion rejected: entry total {total} exceeds the row's amount {cap}")
    return Checked({
        "description": str(raw.get("description", ""))[:300] or "Reconciliation correction",
        "lines": [{"account_code": l.account_code, "direction": l.direction.value,
                   "amount_paise": l.amount_paise} for l in lines],
    }, None)


def case_facts(item: ReconciliationItem) -> dict:
    """What the model sees about one discrepancy: facts only, no customer data."""
    facts = {
        "ref": str(item.position),
        "status": item.status,
        "entity_type": item.entity_type,
        "entity_id": item.entity_id,
        "report_amount_paise": item.report_amount_paise,
        "ledger_amount_paise": item.ledger_amount_paise,
        "report_fee_paise": item.report_fee_paise,
        "ledger_fee_paise": item.ledger_fee_paise,
    }
    if item.report_row:
        facts["report_row"] = {k: v for k, v in item.report_row.items()
                               if k in ("description", "settled_at", "order_id", "tax")}
    return facts


def explain_items(session: Session, items: Sequence[ReconciliationItem], explainer: Explainer,
                  batch_size: int = 10) -> None:
    """Fill ai_* fields on every non-matched item. Failures are recorded, never raised."""
    todo = [i for i in items if i.status != ReconStatus.MATCHED.value]
    accounts = [{"code": a.code, "name": a.name, "type": a.type} for a in session.scalars(select(Account))]
    codes = {a["code"] for a in accounts}

    for start in range(0, len(todo), batch_size):  # batching = fewer calls under free-tier rate limits
        batch = todo[start:start + batch_size]
        by_ref = {str(i.position): i for i in batch}
        try:
            results = explainer.explain([case_facts(i) for i in batch], accounts)
        except Exception as e:  # noqa: BLE001
            for i in batch:
                i.ai_error = f"{type(e).__name__}: {e}"[:1000]
            continue
        for res in results:
            item = by_ref.pop(str(res.get("ref")), None)
            if item is None:
                continue  # model invented a ref: ignore
            cause = res.get("likely_cause")
            item.ai_explanation = str(res.get("explanation", ""))[:2000]
            item.ai_cause = cause if cause in CAUSES else "other"
            item.ai_confidence = res.get("confidence") if res.get("confidence") in ("low", "medium", "high") else "low"
            checked = check_suggestion(res.get("suggested_entry"), codes, item)
            item.ai_suggestion, item.ai_error = checked.suggestion, checked.error
        for item in by_ref.values():
            item.ai_error = "AI returned no result for this row"
