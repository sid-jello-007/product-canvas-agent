"""The workflow, end to end, in two stages with a human checkpoint between them.

Stage 1  idea / docs / designs -> guardrails -> brief -> product canvas
         (the user reviews and edits the canvas: human in the loop)
Stage 2  canvas -> spec -> tickets -> evaluate -> refine weak stories -> evaluate again
         -> duplicate check -> value KPIs -> exports

The checkpoint matters: the canvas is where business judgement lives, so a
person signs it off before the agents spend tokens on the detailed backlog.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import agents
from .config import SETTINGS, Settings
from .evals import QualityReport, evaluate, find_duplicates
from .guardrails import apply_moderation, check_inputs
from .ingest import Context, build_context
from .llm import LLM
from .schemas import Critique, Epic, ProductCanvas, ProductSpec, TicketPlan


@dataclass
class CanvasResult:
    canvas: ProductCanvas
    context: Context
    warnings: list[str] = field(default_factory=list)


@dataclass
class BacklogResult:
    spec: ProductSpec
    plan: TicketPlan
    quality: QualityReport
    first_pass_score: int
    kpis: dict
    notes: list[str] = field(default_factory=list)


def build_canvas(idea: str, files: list[str], llm: LLM, settings: Settings = SETTINGS) -> CanvasResult:
    check_inputs(idea, files, settings.limits)
    context = build_context(idea, files, llm, settings.limits.max_context_chars)
    warnings = apply_moderation(llm.moderate(context.as_prompt()))
    if context.truncated:
        warnings.append("Input was longer than the context budget and was truncated.")
    canvas = agents.canvas_agent(llm, context.as_prompt())
    return CanvasResult(canvas=canvas, context=context, warnings=warnings)


def _replace_stories(plan: TicketPlan, fixed: list) -> TicketPlan:
    by_key = {s.key: s for s in fixed}
    epics = [
        Epic(key=e.key, title=e.title, summary=e.summary, stories=[by_key.get(s.key, s) for s in e.stories])
        for e in plan.epics
    ]
    return TicketPlan(epics=epics)


def build_backlog(canvas: ProductCanvas, context_prompt: str, llm: LLM, settings: Settings = SETTINGS) -> BacklogResult:
    notes: list[str] = []
    spec = agents.spec_agent(llm, canvas, context_prompt)
    plan = agents.ticket_agent(llm, spec)

    critique = agents.critic_agent(llm, plan)
    report = evaluate(plan, spec, critique)
    first_pass = report.overall

    # Self correction loop: send only the weak stories back, then re-review only those.
    refined: list[str] = []
    for _ in range(settings.limits.max_refine_rounds):
        failing = report.failing_keys(settings.limits.pass_score)
        if not failing:
            break
        weak = [s for s in plan.all_stories() if s.key in failing]
        fixed = agents.refine_agent(llm, spec, weak, report.combined_issues())
        if not fixed:
            break
        plan = _replace_stories(plan, fixed)
        refined += [s.key for s in fixed]
        recheck = agents.critic_agent(llm, TicketPlan(epics=[Epic(key="R", title="Refined", summary="", stories=fixed)]))
        merged = {r.key: r for r in critique.reviews}
        merged.update({r.key: r for r in recheck.reviews})
        critique = Critique(reviews=list(merged.values()), overall_comment=critique.overall_comment)
        report = evaluate(plan, spec, critique)

    report.refined_keys = sorted(set(refined))

    # Duplicate detection is useful but not critical: degrade gracefully if it fails.
    stories = plan.all_stories()
    if len(stories) > 1:
        try:
            vectors = llm.embed([f"{s.title}. {s.user_story}" for s in stories])
            report.duplicates = find_duplicates(stories, vectors, settings.limits.duplicate_threshold)
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Duplicate check skipped: {exc}")

    kpis = value_kpis(len(stories), llm, settings)
    return BacklogResult(spec=spec, plan=plan, quality=report, first_pass_score=first_pass, kpis=kpis, notes=notes)


def value_kpis(story_count: int, llm: LLM, settings: Settings = SETTINGS) -> dict:
    """Translate the run into business terms a sponsor cares about: time saved versus cost."""
    v = settings.value
    totals = llm.telemetry.totals()
    manual_hours = v.pm_hours_per_spec + story_count * v.pm_minutes_per_story / 60
    return {
        "stories": story_count,
        "manual_hours_estimate": round(manual_hours, 1),
        "manual_cost_gbp": round(manual_hours * v.hourly_rate_gbp),
        "run_seconds": totals["seconds"],
        "run_cost_usd": totals["cost_usd"],
        "assumptions": f"{v.pm_hours_per_spec:g} h per spec, {v.pm_minutes_per_story:g} min per story, £{v.hourly_rate_gbp:g}/h",
    }
