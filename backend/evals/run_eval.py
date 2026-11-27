"""Run the reconciliation eval against the configured Gemini model.

  make eval
Prints per-case results + accuracy, and saves evals/results/<model>.md
"""
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings  # noqa: E402
from app.recon.ai import case_facts, get_explainer  # noqa: E402
from app.seed import DEFAULT_ACCOUNTS  # noqa: E402
from evals.scoring import item_for, score  # noqa: E402

HERE = Path(__file__).parent
ACCOUNTS = [{"code": c, "name": n, "type": t.value} for c, n, t in DEFAULT_ACCOUNTS]
CODES = {a["code"] for a in ACCOUNTS}


def run(explainer, cases: list[dict], batch_size: int = 10) -> list:
    answers: dict[str, dict] = {}
    for start in range(0, len(cases), batch_size):
        batch = cases[start:start + batch_size]
        facts = []
        for n, c in enumerate(batch):
            item = item_for(c["facts"])
            item.position = start + n
            facts.append(case_facts(item))
        for res in explainer.explain(facts, ACCOUNTS):
            answers[str(res.get("ref"))] = res
    return [score(c, answers.get(str(i)), CODES) for i, c in enumerate(cases)]


def main() -> None:
    explainer = get_explainer()
    if explainer is None:
        sys.exit("GEMINI_API_KEY is not set in .env")
    cases = json.loads((HERE / "recon_cases.json").read_text())
    t0 = time.perf_counter()
    scores = run(explainer, cases)
    secs = time.perf_counter() - t0

    n = len(scores)
    pct = lambda k: 100 * sum(getattr(s, k) for s in scores) / n  # noqa: E731
    lines = [f"# Reconciliation eval: {settings.gemini_model}", "",
             f"{datetime.now(UTC):%Y-%m-%d %H:%M} UTC · {n} cases · {secs:.0f}s", "",
             "| Metric | Score |", "|---|---|",
             f"| Correct cause | {pct('cause_ok'):.0f}% |",
             f"| Suggestions passing guardrails | {pct('guardrails_ok'):.0f}% |",
             f"| Correct journal entry (or correctly none) | {pct('entry_ok'):.0f}% |",
             f"| **Fully correct** | **{pct('fully_correct'):.0f}%** |", "",
             "| Case | Cause | Entry | Detail |", "|---|---|---|---|"]
    for s in scores:
        lines.append(f"| {s.name} | {'✓' if s.cause_ok else '✗'} | {'✓' if s.entry_ok else '✗'} | {s.detail} |")
    report = "\n".join(lines)
    out = HERE / "results" / f"{settings.gemini_model}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(report + "\n")
    print(report)
    print(f"\nSaved {out.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
