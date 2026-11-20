"""Benchmark the workflow on a fixed set of ideas and write a scorecard.

Run this whenever you change a prompt or a model, and compare the scorecard
with the previous one. It is the offline equivalent of a pilot's KPI review:
quality, refinement lift, latency and cost per run.

    MISTRAL_API_KEY=... python -m evals.run_evals            # real models
    python -m evals.run_evals --demo                          # wiring check, no key needed
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from canvas.llm import FakeLLM, MistralLLM
from canvas.pipeline import build_backlog, build_canvas
from canvas.telemetry import Telemetry

HERE = Path(__file__).parent


def run(demo: bool, limit: int | None, pause: float) -> Path:
    cases = json.loads((HERE / "golden_set.json").read_text())[:limit]
    rows = []
    for case in cases:
        telemetry = Telemetry()
        llm = FakeLLM(telemetry) if demo else MistralLLM(telemetry=telemetry)
        try:
            c = build_canvas(case["idea"], [], llm)
            r = build_backlog(c.canvas, c.context.as_prompt(), llm)
            t = telemetry.totals()
            rows.append({
                "id": case["id"], "status": "ok", "stories": len(r.plan.all_stories()),
                "first_pass": r.first_pass_score, "final": r.quality.overall,
                "rule_pass": round(r.quality.rule_pass_rate, 2), "judge": round(r.quality.avg_judge_score, 2),
                "uncovered": len(r.quality.uncovered_requirements), "duplicates": len(r.quality.duplicates),
                "refined": len(r.quality.refined_keys), "seconds": t["seconds"], "cost_usd": t["cost_usd"],
            })
        except Exception as exc:  # noqa: BLE001
            rows.append({"id": case["id"], "status": f"error: {exc}"[:120]})
        print(rows[-1])
        time.sleep(pause)  # stay inside free tier rate limits

    ok = [r for r in rows if r["status"] == "ok"]
    avg = lambda k: round(sum(r[k] for r in ok) / len(ok), 2) if ok else 0  # noqa: E731
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Eval scorecard ({'demo' if demo else 'live Mistral'}, {stamp})", "",
        f"Cases: {len(rows)} | succeeded: {len(ok)} | avg final score: {avg('final')} | "
        f"avg lift from refinement: {round(avg('final') - avg('first_pass'), 1)} | "
        f"avg seconds: {avg('seconds')} | avg cost: ${avg('cost_usd')}", "",
        "| Case | Stories | First pass | Final | Rules pass | Judge | Uncovered reqs | Duplicates | Refined | Seconds | Cost $ |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r["status"] != "ok":
            lines.append(f"| {r['id']} | {r['status']} |" + " |" * 10)
            continue
        lines.append(
            f"| {r['id']} | {r['stories']} | {r['first_pass']} | {r['final']} | {r['rule_pass']:.0%} | {r['judge']} | "
            f"{r['uncovered']} | {r['duplicates']} | {r['refined']} | {r['seconds']} | {r['cost_usd']} |"
        )
    out = HERE / "results" / ("scorecard_demo.md" if demo else "scorecard.md")
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {out}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use the fake model (no API key)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--pause", type=float, default=2.0, help="seconds between cases")
    args = ap.parse_args()
    run(args.demo, args.limit, 0 if args.demo else args.pause)
