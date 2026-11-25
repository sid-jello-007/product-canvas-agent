"""Benchmark the workflow on a fixed set of ideas and write a scorecard.

Run this whenever you change a prompt or a model, and compare the scorecard
with the previous one. It is the offline equivalent of a pilot's KPI review:
spec validity, plan coverage, how often the first build passes, fix rounds,
latency and cost per run.

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
from canvas.pipeline import fast_forward
from canvas.telemetry import Telemetry

HERE = Path(__file__).parent


def run(demo: bool, limit: int | None, pause: float) -> Path:
    cases = json.loads((HERE / "golden_set.json").read_text())[:limit]
    rows = []
    for case in cases:
        telemetry = Telemetry()
        llm = FakeLLM(telemetry) if demo else MistralLLM(telemetry=telemetry)
        try:
            r = fast_forward(case["idea"], [], "", [], None, llm)
            t = telemetry.totals()
            results = r.review.results
            first = r.build_rounds[0].split(":")[1].split(" scenarios")[0].strip()
            rows.append({
                "id": case["id"], "status": "ok",
                "reqs": sum(len(c.requirements) for c in r.spec.capabilities),
                "spec_errors": len(r.spec_report.errors), "conflicts": len(r.spec.conflicts),
                "plan_errors": len(r.plan_report.errors), "static_errors": len(r.static_report.errors),
                "first_build": first, "final": f"{sum(x.status == 'pass' for x in results)}/{len(results)}",
                "fix_rounds": len(r.build_rounds) - 1, "seconds": t["seconds"], "cost_usd": t["cost_usd"],
            })
        except Exception as exc:  # noqa: BLE001
            rows.append({"id": case["id"], "status": f"error: {exc}"[:120]})
        print(rows[-1])
        time.sleep(pause)  # stay inside free tier rate limits

    ok = [r for r in rows if r["status"] == "ok"]
    avg = lambda k: round(sum(r[k] for r in ok) / len(ok), 2) if ok else 0  # noqa: E731
    clean = sum(1 for r in ok if not (r["spec_errors"] or r["plan_errors"] or r["static_errors"]))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Eval scorecard ({'demo' if demo else 'live Mistral'}, {stamp})", "",
        f"Cases: {len(rows)} | completed: {len(ok)} | clean on every check: {clean} | "
        f"avg seconds: {avg('seconds')} | avg cost: ${avg('cost_usd')}", "",
        "| Case | Reqs | Spec errors | Conflicts | Plan errors | Static errors | First build | Final | Fix rounds | Seconds | Cost $ |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r["status"] != "ok":
            lines.append(f"| {r['id']} | {r['status']} |" + " |" * 10)
            continue
        lines.append(
            f"| {r['id']} | {r['reqs']} | {r['spec_errors']} | {r['conflicts']} | {r['plan_errors']} | {r['static_errors']} | "
            f"{r['first_build']} | {r['final']} | {r['fix_rounds']} | {r['seconds']} | {r['cost_usd']} |"
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
