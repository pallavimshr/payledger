"""Parse a Razorpay-style settlement report CSV.

Expected columns (a simplified version of Razorpay's settlement recon report):
  entity_id, type, amount, fee, tax, currency, order_id, settlement_id, settled_at

Amounts in the report are in RUPEES as text ("1499.00"); we convert them to
integer paise with Decimal so no floating-point error can creep in.
"""
import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

REQUIRED = {"entity_id", "type", "amount", "fee"}
TYPES = {"payment", "refund", "adjustment"}


class ReportError(ValueError):
    pass


@dataclass(frozen=True)
class ReportRow:
    line: int
    entity_id: str
    type: str
    amount_paise: int
    fee_paise: int
    raw: dict = field(hash=False, compare=False)


def to_paise(text: str, line: int, column: str) -> int:
    value = (text or "0").strip().replace(",", "")
    try:
        paise = Decimal(value) * 100
    except InvalidOperation:
        raise ReportError(f"Line {line}: {column} '{text}' is not a number")
    if paise != paise.to_integral_value():
        raise ReportError(f"Line {line}: {column} '{text}' has more than 2 decimal places")
    return int(paise)


def parse_report(data: bytes) -> list[ReportRow]:
    try:
        text = data.decode("utf-8-sig")  # handles Excel's BOM
    except UnicodeDecodeError:
        raise ReportError("File is not UTF-8 text. Upload the CSV export, not an Excel file.")
    reader = csv.DictReader(io.StringIO(text))
    headers = {h.strip().lower() for h in (reader.fieldnames or [])}
    missing = REQUIRED - headers
    if missing:
        raise ReportError(f"Missing column(s): {', '.join(sorted(missing))}")

    rows: list[ReportRow] = []
    seen: set[tuple[str, str]] = set()
    for i, raw in enumerate(reader, start=2):  # line 1 is the header
        r = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        if not any(r.values()):
            continue  # skip blank lines
        kind = r["type"].lower()
        if kind not in TYPES:
            raise ReportError(f"Line {i}: unknown type '{r['type']}' (expected {', '.join(sorted(TYPES))})")
        if not r["entity_id"]:
            raise ReportError(f"Line {i}: entity_id is empty")
        if (kind, r["entity_id"]) in seen:
            raise ReportError(f"Line {i}: duplicate row for {kind} {r['entity_id']}")
        seen.add((kind, r["entity_id"]))
        rows.append(ReportRow(
            line=i, entity_id=r["entity_id"], type=kind,
            amount_paise=to_paise(r["amount"], i, "amount"),
            fee_paise=to_paise(r.get("fee", ""), i, "fee"),
            raw=r,
        ))
    if not rows:
        raise ReportError("The report has no rows")
    return rows
