"""The flow, stage by stage, with a human checkpoint between each.

01 Domain store (no target code access)
   inputs -> guardrails -> product canvas + architecture        [C0: approve inputs]
          -> spec agent: normalise, clarify, validate           [C1: approve shared spec]
             (conflicts come back as questions, never guesses)
02 Delivery to the target (first code access is here)
   explore -> design                                            [C2: approve design]
   tasks + QA plan -> tests written first (RED)                 [C3: approve plan]
   build (GREEN) -> static checks + independent QA review
   -> failure triage -> fix -> re-check                         [C4: verify + approve]

Each stage function takes the run so far, adds its artefacts and returns it.
The UI decides when to call the next one; fast_forward calls them all.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import agents
from .config import SETTINGS, Settings
from .evals import Report, near_duplicates, static_checks, validate_canvas, validate_plan, validate_spec
from .guardrails import apply_moderation, check_inputs
from .ingest import build_context
from .llm import LLM
from .schemas import Architecture, DesignDoc, Exploration, ProductCanvas, QAReview, SpecPackage, TaskPlan
from .telemetry import Telemetry


@dataclass
class Run:
    po_context: str = ""
    arch_inputs: str = ""
    target_code: str = ""
    sources_summary: str = ""
    warnings: list[str] = field(default_factory=list)
    answers: str = ""
    resolutions: str = ""
    canvas: ProductCanvas | None = None
    arch: Architecture | None = None
    spec: SpecPackage | None = None
    explore: Exploration | None = None
    design: DesignDoc | None = None
    plan: TaskPlan | None = None
    tests: str = ""
    html: str = ""
    review: QAReview | None = None
    canvas_report: Report = field(default_factory=Report)
    spec_report: Report = field(default_factory=Report)
    plan_report: Report = field(default_factory=Report)
    static_report: Report = field(default_factory=Report)
    build_rounds: list[str] = field(default_factory=list)
    approvals: list[str] = field(default_factory=list)
    telemetry: Telemetry = field(default_factory=Telemetry)


# ---------------- 01 Domain store ----------------

def stage_inputs(idea: str, po_files: list[str], arch_text: str, arch_files: list[str], target_file: str | None,
                 llm: LLM, settings: Settings = SETTINGS) -> Run:
    """Guardrails and ingest. PO inputs, architecture inputs and target code are kept apart on purpose."""
    run = Run(telemetry=llm.telemetry)
    all_files = (po_files or []) + (arch_files or []) + ([target_file] if target_file else [])
    check_inputs(idea or arch_text, all_files, settings.limits)

    po = build_context(idea, po_files, llm, settings.limits.max_context_chars)
    arch = build_context(arch_text, arch_files, llm, settings.limits.max_context_chars // 2)
    run.po_context, run.arch_inputs = po.as_prompt(), arch.as_prompt()
    if target_file:
        run.target_code = Path(target_file).read_text(encoding="utf-8", errors="replace")[:40_000]

    run.sources_summary = "PO inputs: " + (po.summary() or "none") + " | Architecture inputs: " + (arch.summary() or "none")
    if target_file:
        run.sources_summary += f" | Target code: {Path(target_file).name} (held back until Explore)"
    run.warnings = apply_moderation(llm.moderate(run.po_context + "\n" + run.arch_inputs))
    if po.truncated or arch.truncated:
        run.warnings.append("Some input was longer than the context budget and was truncated.")
    return run


def stage_canvas(run: Run, llm: LLM, answers: str = "") -> Run:
    """Product canvas and architecture, drafted side by side. Neither agent sees target code."""
    run.answers = answers or run.answers
    run.canvas = agents.canvas_agent(llm, run.po_context, run.answers)
    run.arch = agents.architecture_agent(llm, run.canvas, run.arch_inputs)
    run.canvas_report = validate_canvas(run.canvas)
    return run


def stage_spec(run: Run, llm: LLM, resolutions: str = "") -> Run:
    """Normalise, clarify, validate. Conflicts are surfaced as questions and block approval."""
    run.resolutions = resolutions or run.resolutions
    run.spec = agents.spec_agent(llm, run.canvas, run.arch, run.resolutions)
    run.spec_report = validate_spec(run.spec, run.canvas, run.arch)
    reqs = [(f"{c.name} / {r.name}", r.statement) for c in run.spec.capabilities for r in c.requirements]
    if len(reqs) > 1:
        try:
            vectors = llm.embed([s for _, s in reqs])
            for a, b, sim in near_duplicates([n for n, _ in reqs], vectors):
                run.spec_report.warn(f"{a} and {b}", f"Requirements look like duplicates (similarity {sim})")
        except Exception as exc:  # noqa: BLE001  (duplicate check is helpful, not critical)
            run.spec_report.warn("embeddings", f"Duplicate check skipped: {exc}")
    return run


# ---------------- 02 Delivery ----------------

def stage_design(run: Run, llm: LLM) -> Run:
    """First access to target code happens here, after the spec is approved."""
    run.explore = agents.explore_agent(llm, run.spec, run.target_code)
    run.design = agents.design_agent(llm, run.spec, run.arch, run.explore)
    return run


def stage_plan(run: Run, llm: LLM) -> Run:
    """Tasks and QA plan, then the tests are written before any code (RED)."""
    run.plan = agents.task_agent(llm, run.spec, run.design)
    run.plan_report = validate_plan(run.plan, run.spec)
    run.tests = agents.qa_automation_agent(llm, run.plan, run.design)
    return run


def _failures_for_builder(run: Run) -> str:
    lines = [f"- Static check: {f.where}: {f.message}" for f in run.static_report.errors]
    lines += [f"- Scenario '{r.scenario}': {r.evidence}" for r in run.review.results if r.status == "fail" and r.owner == "app"]
    return "\n".join(lines)


def stage_build(run: Run, llm: LLM, settings: Settings = SETTINGS) -> Run:
    """Build (GREEN), check, triage failures to their owner, fix app failures, check again."""
    run.html = agents.build_agent(llm, run.spec, run.design, run.plan, run.tests, run.target_code)
    run.build_rounds = []
    for round_no in range(settings.limits.max_fix_rounds + 1):
        run.static_report = static_checks(run.html, run.tests, run.plan)
        static_issues = [f"{f.where}: {f.message}" for f in run.static_report.errors]
        run.review = agents.qa_review_agent(llm, run.spec, run.html, run.tests, static_issues)
        failing = [r for r in run.review.results if r.status == "fail"]
        app_failures = _failures_for_builder(run)
        routed = sorted({r.owner for r in failing if r.owner in ("test", "spec")})
        note = f"Round {round_no + 1}: {len(run.review.results) - len(failing)}/{len(run.review.results)} scenarios pass"
        if run.static_report.errors:
            note += f", {len(run.static_report.errors)} static errors"
        if routed:
            note += f"; routed to {', '.join(routed)} owner for a decision"
        run.build_rounds.append(note)
        if not app_failures or round_no == settings.limits.max_fix_rounds:
            break
        run.html = agents.build_agent(llm, run.spec, run.design, run.plan, run.tests,
                                      failures=app_failures, current_html=run.html)
    return run


def value_kpis(run: Run, settings: Settings = SETTINGS) -> dict:
    """Translate the run into a sponsor's terms: effort replaced versus model cost."""
    v = settings.value
    t = run.telemetry.totals()
    hours = v.pm_hours_per_spec + (v.dev_hours_per_prototype if run.html else 0)
    passed = sum(r.status == "pass" for r in run.review.results) if run.review else 0
    total = len(run.review.results) if run.review else 0
    reqs = sum(len(c.requirements) for c in run.spec.capabilities) if run.spec else 0
    return {
        "requirements": reqs,
        "scenarios_passing": f"{passed}/{total}" if total else "not built yet",
        "manual_hours_estimate": hours,
        "manual_cost_gbp": round(hours * v.hourly_rate_gbp),
        "run_seconds": t["seconds"],
        "run_cost_usd": t["cost_usd"],
        "calls": t["calls"],
        "assumptions": f"{v.pm_hours_per_spec:g} h for canvas and spec, {v.dev_hours_per_prototype:g} h for design, tests "
                       f"and prototype, £{v.hourly_rate_gbp:g}/h",
    }


def fast_forward(idea: str, po_files: list[str], arch_text: str, arch_files: list[str], target_file: str | None,
                 llm: LLM, settings: Settings = SETTINGS) -> Run:
    """Every stage with automatic approval, like OpenSpec's fast-forward. Conflicts are recorded, not resolved."""
    run = stage_inputs(idea, po_files, arch_text, arch_files, target_file, llm, settings)
    for stage in (stage_canvas, stage_spec, stage_design, stage_plan):
        run = stage(run, llm)
    run = stage_build(run, llm, settings)
    run.approvals.append("All checkpoints auto-approved (fast-forward)")
    return run
