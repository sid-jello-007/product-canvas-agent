"""The agents. Each has one job, one skill file and one output contract.

Agent instructions live in skills/<name>/SKILL.md, in the open Agent Skills
format (a name, a description and plain instructions). Keeping them as files
means a product owner can read and change an agent's behaviour without touching
Python, and the same skills can be reused by other agent tools.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .config import SETTINGS
from .guardrails import UNTRUSTED_CONTENT_RULE
from .llm import LLM, to_json
from .schemas import (
    Architecture, DesignDoc, Exploration, ProductCanvas, QAReview, SpecPackage, TaskPlan,
)

M = SETTINGS.models
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


@lru_cache(maxsize=None)
def skill(name: str) -> str:
    """Load a skill's instructions (the body after the YAML front matter)."""
    raw = (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
    body = re.sub(r"^---\n.*?\n---\n", "", raw, count=1, flags=re.DOTALL)
    return body.strip() + "\n\n" + UNTRUSTED_CONTENT_RULE


def extract_code(text: str, lang: str) -> str:
    """Pull the first fenced code block of the given language out of a model reply."""
    match = re.search(rf"```{lang}\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if not match:
        match = re.search(r"```[a-zA-Z]*\s*\n(.*?)```", text, re.DOTALL)
    return (match.group(1) if match else text).strip()


# ---------------- 01 Domain store ----------------

def canvas_agent(llm: LLM, po_context: str, answers: str = "") -> ProductCanvas:
    user = po_context + (f"\n\nAnswers from the product owner:\n{answers}" if answers.strip() else "")
    return llm.structured("canvas agent", M.generate, skill("product-canvas"), user, ProductCanvas)


def architecture_agent(llm: LLM, canvas: ProductCanvas, arch_inputs: str) -> Architecture:
    user = (
        f"Architecture inputs:\n<source name=\"architecture inputs\" kind=\"text\">\n{arch_inputs or '(none provided)'}\n</source>\n\n"
        f"The change being designed:\n{to_json(canvas)}"
    )
    return llm.structured("architecture agent", M.generate, skill("architecture"), user, Architecture)


def spec_agent(llm: LLM, canvas: ProductCanvas, arch: Architecture, resolutions: str = "") -> SpecPackage:
    user = f"Approved product canvas:\n{to_json(canvas)}\n\nApproved architecture:\n{to_json(arch)}"
    if resolutions.strip():
        user += f"\n\nAnswers to earlier conflicts (apply these):\n{resolutions}"
    return llm.structured("spec agent", M.generate, skill("spec-author"), user, SpecPackage)


# ---------------- 02 Delivery ----------------

def explore_agent(llm: LLM, spec: SpecPackage, target_code: str) -> Exploration:
    user = (
        f"Approved spec:\n{to_json(spec)}\n\nTarget code:\n"
        + (f"<source name=\"target\" kind=\"code\">\n{target_code}\n</source>" if target_code else "(none: greenfield)")
    )
    return llm.structured("explore agent", M.generate, skill("explore"), user, Exploration)


def design_agent(llm: LLM, spec: SpecPackage, arch: Architecture, explore: Exploration) -> DesignDoc:
    user = f"Spec:\n{to_json(spec)}\n\nArchitecture:\n{to_json(arch)}\n\nExplore findings:\n{to_json(explore)}"
    return llm.structured("design agent", M.generate, skill("design"), user, DesignDoc)


def task_agent(llm: LLM, spec: SpecPackage, design: DesignDoc) -> TaskPlan:
    user = f"Spec:\n{to_json(spec)}\n\nDesign:\n{to_json(design)}"
    return llm.structured("planning agent", M.generate, skill("task-planner"), user, TaskPlan)


def qa_automation_agent(llm: LLM, plan: TaskPlan, design: DesignDoc) -> str:
    user = (
        f"QA plan:\n{json.dumps([t.model_dump() for t in plan.qa_plan], indent=2)}\n\n"
        f"UI structure and test ids from the design:\n" + "\n".join(f"- {u}" for u in design.ui_structure)
    )
    return extract_code(llm.text("QA automation agent (tests first)", M.code, skill("qa-automation"), user), "javascript")


def build_agent(llm: LLM, spec: SpecPackage, design: DesignDoc, plan: TaskPlan, tests: str,
                target_code: str = "", failures: str = "", current_html: str = "") -> str:
    if failures:
        step = "implementation agent (fix)"
        user = f"Current app:\n```html\n{current_html}\n```\n\nQA failures to fix:\n{failures}\n\nTests:\n```javascript\n{tests}\n```"
    else:
        step = "implementation agent (build)"
        user = (
            f"Spec:\n{to_json(spec)}\n\nDesign:\n{to_json(design)}\n\nTasks:\n{to_json(plan)}\n\n"
            f"Tests that must pass:\n```javascript\n{tests}\n```"
        )
        if target_code:
            user += f"\n\nExisting target code to evolve (keep what still fits):\n```html\n{target_code}\n```"
    return extract_code(llm.text(step, M.code, skill("implementation"), user), "html")


def qa_review_agent(llm: LLM, spec: SpecPackage, html: str, tests: str, static_issues: list[str]) -> QAReview:
    scenarios = [s.name for c in spec.capabilities for r in c.requirements for s in r.scenarios]
    user = (
        f"Scenarios to check: {json.dumps(scenarios)}\n\nSpec:\n{to_json(spec)}\n\n"
        f"Static check findings: {json.dumps(static_issues)}\n\n"
        f"App code:\n```html\n{html}\n```\n\nTests:\n```javascript\n{tests}\n```"
    )
    return llm.structured("QA review agent", M.review, skill("qa-review"), user, QAReview)
