"""The four agents. Each has one job, one prompt and one output contract.

Splitting the work this way mirrors how a product team works (discovery,
spec, backlog, review) and makes each step testable and swappable: you can
change the model or prompt of one agent without touching the others.
"""
from __future__ import annotations

import json

from .config import SETTINGS
from .guardrails import UNTRUSTED_CONTENT_RULE
from .llm import LLM, to_json
from .schemas import Critique, ProductCanvas, ProductSpec, RefinedStories, Story, TicketPlan

M = SETTINGS.models

CANVAS_SYSTEM = f"""You are a senior product manager running discovery.
Turn the material provided into a product canvas. Be specific and grounded in the material;
where the material is silent, make a sensible assumption and list it under assumptions_and_risks,
and put genuine unknowns under open_questions. Success metrics must have numeric targets.
{UNTRUSTED_CONTENT_RULE}"""

SPEC_SYSTEM = f"""You are a senior product manager writing a product spec (PRD) from an agreed product canvas.
Write 4 to 10 functional requirements with ids FR-1, FR-2, ... Each must be specific and testable.
Use MoSCoW priority (Must, Should, Could). Keep the MVP tight: only the core job is Must.
{UNTRUSTED_CONTENT_RULE}"""

TICKETS_SYSTEM = """You are a delivery lead turning a product spec into a Jira backlog.
Rules:
- Group stories into 2 to 5 epics with keys E1, E2, ... and story keys E1-S1, E1-S2, ...
- user_story must read: "As a <user>, I want <goal>, so that <benefit>."
- 2 to 4 acceptance criteria per story, each written as "Given ..., when ..., then ...".
- story_points must be a Fibonacci number: 1, 2, 3, 5, 8 or 13. Split anything bigger than 8.
- Every Must and Should requirement must be covered by at least one story (list ids in requirement_ids).
- dependencies lists keys of stories that must ship first."""

CRITIC_SYSTEM = """You are a strict agile coach reviewing user stories against INVEST
(Independent, Negotiable, Valuable, Estimable, Small, Testable).
Score each story 1 to 5. List concrete issues for anything below 4. Do not rewrite stories."""

REFINE_SYSTEM = """You are a delivery lead fixing user stories that failed review.
Rewrite only the stories given, keeping their keys. Fix every issue listed while following the backlog rules:
"As a..., I want..., so that..." user stories, 2 to 4 "Given..., when..., then..." acceptance criteria,
Fibonacci story points, and requirement_ids that point at real spec requirements."""


def canvas_agent(llm: LLM, context_prompt: str) -> ProductCanvas:
    return llm.structured("agent: canvas", M.generate, CANVAS_SYSTEM, context_prompt, ProductCanvas)


def spec_agent(llm: LLM, canvas: ProductCanvas, context_prompt: str) -> ProductSpec:
    user = f"Agreed product canvas:\n{to_json(canvas)}\n\nOriginal material for reference:\n{context_prompt}"
    return llm.structured("agent: spec", M.generate, SPEC_SYSTEM, user, ProductSpec)


def ticket_agent(llm: LLM, spec: ProductSpec) -> TicketPlan:
    return llm.structured("agent: tickets", M.generate, TICKETS_SYSTEM, f"Product spec:\n{to_json(spec)}", TicketPlan)


def critic_agent(llm: LLM, plan: TicketPlan) -> Critique:
    return llm.structured("agent: critic", M.judge, CRITIC_SYSTEM, f"Stories to review:\n{to_json(plan)}", Critique)


def refine_agent(llm: LLM, spec: ProductSpec, stories: list[Story], issues: dict[str, list[str]]) -> list[Story]:
    payload = [{"story": s.model_dump(), "issues": issues.get(s.key, [])} for s in stories]
    user = (
        f"Spec requirement ids available: {[r.id for r in spec.requirements]}\n\n"
        f"Stories to fix:\n{json.dumps(payload, indent=2)}"
    )
    return llm.structured("agent: refine", M.generate, REFINE_SYSTEM, user, RefinedStories).stories
