"""Check the Gemini setup: is the key valid, which models are available, does the configured one work?

  make ai-check
Never prints the key itself.
"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings  # noqa: E402
from app.recon.ai import AIError, GeminiExplainer  # noqa: E402

key = settings.gemini_api_key
if not key:
    sys.exit("GEMINI_API_KEY is not set. Add it to the .env file in the project root.")
print(f"Key found ({key[:4]}…{key[-2:]}, {len(key)} chars). Configured model: {settings.gemini_model}")

try:
    r = httpx.get("https://generativelanguage.googleapis.com/v1beta/models",
                  headers={"x-goog-api-key": key}, params={"pageSize": 200}, timeout=30)
except httpx.HTTPError as e:
    sys.exit(f"Could not reach Google: {e}")
if r.status_code != 200:
    sys.exit(f"Key rejected by Google ({r.status_code}): {r.text[:300]}")
models = [m["name"].removeprefix("models/") for m in r.json().get("models", [])
          if "generateContent" in m.get("supportedGenerationMethods", [])]
flash = [m for m in models if "flash" in m]
print(f"\nYour key can use {len(models)} text models. Flash models (fast, free tier):")
for m in flash[:15]:
    print("  -", m)

import time  # noqa: E402

print(f"\nTest call to {settings.gemini_model} …")
t0 = time.perf_counter()
case = {"ref": "0", "status": "fee_mismatch", "entity_type": "payment", "entity_id": "pay_TEST",
        "report_amount_paise": 100000, "ledger_amount_paise": 100000,
        "report_fee_paise": 3540, "ledger_fee_paise": 2360}
accounts = [{"code": "expenses:gateway_fees", "name": "Gateway fees", "type": "expense"},
            {"code": "assets:razorpay_clearing", "name": "Held by Razorpay", "type": "asset"},
            {"code": "revenue:sales", "name": "Sales", "type": "revenue"}]
try:
    res = GeminiExplainer(key, settings.gemini_model).explain([case], accounts)[0]
except AIError as e:
    sys.exit(f"FAILED: {e}\nTry another model: add GEMINI_MODEL=<one of the names above> to .env")
print(f"OK in {time.perf_counter() - t0:.1f}s. Cause: {res.get('likely_cause')} ({res.get('confidence')})")
print(f"Explanation: {res.get('explanation')}")
print(f"Suggested entry: {res.get('suggested_entry')}")
