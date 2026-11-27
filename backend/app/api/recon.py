"""Reconciliation endpoints: upload a settlement report, review, accept or dismiss fixes."""
import uuid
from collections import Counter

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.ledger import LedgerError, PostingLine, post_entry
from app.models import (
    Direction, ReconciliationItem, ReconciliationRun, ReconStatus, Resolution,
)
from app.recon.ai import explain_items, get_explainer
from app.recon.matcher import match
from app.recon.report import ReportError, parse_report
from app.recon.sample import build_sample_report

router = APIRouter(tags=["reconciliation"])
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _item_out(i: ReconciliationItem) -> dict:
    return {
        "id": i.id, "position": i.position, "entity_type": i.entity_type, "entity_id": i.entity_id,
        "status": i.status, "resolution": i.resolution,
        "report_amount_paise": i.report_amount_paise, "ledger_amount_paise": i.ledger_amount_paise,
        "report_fee_paise": i.report_fee_paise, "ledger_fee_paise": i.ledger_fee_paise,
        "report_row": i.report_row,
        "ai": None if i.ai_explanation is None and i.ai_error is None else {
            "explanation": i.ai_explanation, "cause": i.ai_cause, "confidence": i.ai_confidence,
            "suggestion": i.ai_suggestion, "error": i.ai_error,
        },
    }


def _summary(run: ReconciliationRun) -> dict:
    by_status = Counter(i.status for i in run.items)
    return {
        "id": run.id, "source_filename": run.source_filename, "rows_in_report": run.rows_in_report,
        "ai_model": run.ai_model, "created_at": run.created_at,
        "by_status": dict(by_status),
        "open_items": sum(1 for i in run.items if i.resolution == Resolution.OPEN.value),
    }


def _detail(run: ReconciliationRun) -> dict:
    return {**_summary(run), "items": [_item_out(i) for i in run.items]}


def _run_ai(session: Session, run: ReconciliationRun) -> None:
    explainer = get_explainer()
    if explainer is None:
        return
    explain_items(session, run.items, explainer)
    run.ai_model = explainer.model
    session.commit()


@router.get("/reconciliations/sample-report", response_class=PlainTextResponse)
def sample_report(session: Session = Depends(get_session)):
    """A demo settlement report built from your ledger, with planted discrepancies."""
    return PlainTextResponse(
        build_sample_report(session), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="razorpay_settlement_sample.csv"'},
    )


@router.post("/reconciliations", status_code=201)
def upload_report(file: UploadFile = File(...), session: Session = Depends(get_session)):
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Report is larger than 5 MB")
    try:
        rows = parse_report(data)
    except ReportError as e:
        raise HTTPException(422, str(e))

    run = ReconciliationRun(source_filename=file.filename or "report.csv", rows_in_report=len(rows))
    session.add(run)
    session.flush()
    for item in match(session, rows):
        item.run_id = run.id
        session.add(item)
    session.commit()
    session.refresh(run)
    _run_ai(session, run)  # optional: skipped when no API key is configured
    session.refresh(run)
    return _detail(run)


@router.get("/reconciliations")
def list_runs(session: Session = Depends(get_session)):
    runs = session.scalars(select(ReconciliationRun).order_by(ReconciliationRun.created_at.desc()).limit(50))
    return [_summary(r) for r in runs]


def _get_run(session: Session, run_id: uuid.UUID) -> ReconciliationRun:
    run = session.get(ReconciliationRun, run_id)
    if run is None:
        raise HTTPException(404, "Reconciliation not found")
    return run


@router.get("/reconciliations/{run_id}")
def get_run(run_id: uuid.UUID, session: Session = Depends(get_session)):
    return _detail(_get_run(session, run_id))


@router.post("/reconciliations/{run_id}/explain")
def explain_run(run_id: uuid.UUID, session: Session = Depends(get_session)):
    """(Re)run the AI on this run's open discrepancies."""
    run = _get_run(session, run_id)
    if get_explainer() is None:
        raise HTTPException(400, "No AI configured: add GEMINI_API_KEY to .env and restart the API")
    _run_ai(session, run)
    session.refresh(run)
    return _detail(run)


def _open_item(session: Session, item_id: uuid.UUID) -> ReconciliationItem:
    item = session.get(ReconciliationItem, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    if item.resolution != Resolution.OPEN.value:
        raise HTTPException(409, f"Item is already {item.resolution}")
    return item


@router.post("/reconciliation-items/{item_id}/accept")
def accept_item(item_id: uuid.UUID, session: Session = Depends(get_session)):
    """A person approved the AI's suggested correction: post it to the ledger."""
    item = _open_item(session, item_id)
    s = item.ai_suggestion
    if not s:
        raise HTTPException(400, "This item has no suggested entry to accept")
    lines = [PostingLine(l["account_code"], Direction(l["direction"]), l["amount_paise"]) for l in s["lines"]]
    try:
        entry = post_entry(session, f"[Reconciliation] {s['description']}", lines,
                           idempotency_key=f"recon:{item.id}", commit=False)
    except (LedgerError, IntegrityError) as e:  # validated again: the ledger is the last line of defence
        session.rollback()
        raise HTTPException(422, f"Could not post correction: {e}")
    item.resolution = Resolution.ACCEPTED.value
    item.resolved_entry_id = entry.id
    session.commit()
    return _item_out(item)


@router.post("/reconciliation-items/{item_id}/dismiss")
def dismiss_item(item_id: uuid.UUID, session: Session = Depends(get_session)):
    item = _open_item(session, item_id)
    item.resolution = Resolution.DISMISSED.value
    session.commit()
    return _item_out(item)
