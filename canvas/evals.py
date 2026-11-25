"""Deterministic checks that run at every checkpoint.

These are the 'validate' in normalise, clarify, validate. They are cheap, exact
and never need a model, so they run every time:
- Spec validation follows OpenSpec's rules: SHALL or MUST in every requirement,
  at least one WHEN/THEN scenario each, kebab-case names.
- Traceability: every canvas feature and every NFR reaches the spec, every
  requirement reaches a task, every scenario reaches a test.
- Static build checks: the app is self contained, exposes the reset hook, and
  every test id the tests touch exists in the code.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .schemas import Architecture, ProductCanvas, SpecPackage, TaskPlan

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
NORMATIVE = re.compile(r"\b(SHALL|MUST)\b")
HARNESS_CALL = re.compile(r"\b(?:el|all|click|type|select|text|exists|count)\(\s*['\"`]([a-zA-Z0-9_-]+)['\"`]")
TEST_NAME = re.compile(r"\btest\(\s*(['\"`])(.+?)\1")
EXTERNAL = [
    (re.compile(r"<script[^>]+src=['\"]https?://", re.I), "loads an external script"),
    (re.compile(r"<link[^>]+href=['\"]https?://", re.I), "loads an external stylesheet or font"),
    (re.compile(r"\bfetch\(|XMLHttpRequest|navigator\.sendBeacon|new WebSocket", re.I), "makes network calls"),
]


@dataclass
class Finding:
    level: str  # "error" blocks the checkpoint, "warning" is advisory
    where: str
    message: str


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def error(self, where, msg):
        self.findings.append(Finding("error", where, msg))

    def warn(self, where, msg):
        self.findings.append(Finding("warning", where, msg))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "error"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def markdown(self, title: str) -> str:
        if not self.findings:
            return f"**{title}: all checks passed.**"
        icon = {"error": "❌", "warning": "⚠️"}
        lines = [f"**{title}: {len(self.errors)} errors, {len(self.findings) - len(self.errors)} warnings**"]
        lines += [f"- {icon[f.level]} *{f.where}*: {f.message}" for f in self.findings]
        return "\n".join(lines)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def validate_canvas(canvas: ProductCanvas) -> Report:
    r = Report()
    if not KEBAB.match(canvas.change_id):
        r.error("change_id", f"'{canvas.change_id}' is not kebab-case")
    if not canvas.epics:
        r.error("canvas", "No epics")
    for e in canvas.epics:
        for f in e.features:
            if not f.acceptance_criteria:
                r.error(f"feature '{f.title}'", "No acceptance criteria")
            if not f.test_scenarios:
                r.warn(f"feature '{f.title}'", "No test scenarios")
    return r


def validate_spec(spec: SpecPackage, canvas: ProductCanvas, arch: Architecture) -> Report:
    r = Report()
    names: set[str] = set()
    traced: set[str] = set()
    for cap in spec.capabilities:
        if not KEBAB.match(cap.name):
            r.error(f"capability '{cap.name}'", "Name is not kebab-case")
        if not cap.requirements:
            r.error(f"capability '{cap.name}'", "Has no requirements")
        for req in cap.requirements:
            where = f"{cap.name} / {req.name}"
            if _norm(req.name) in names:
                r.error(where, "Duplicate requirement name")
            names.add(_norm(req.name))
            if not NORMATIVE.search(req.statement):
                r.error(where, "Statement must contain SHALL or MUST")
            if not req.scenarios:
                r.error(where, "Needs at least one scenario")
            for sc in req.scenarios:
                if not sc.when.strip() or not sc.then.strip():
                    r.error(f"{where} / {sc.name}", "Scenario needs both WHEN and THEN")
            if not req.traces_to:
                r.warn(where, "Not traced to a canvas feature or NFR")
            traced |= {_norm(t) for t in req.traces_to}

    for e in canvas.epics:
        for f in e.features:
            if _norm(f.title) not in traced:
                r.error(f"feature '{f.title}'", "Not covered by any requirement")
    for nfr in arch.nfrs:
        if _norm(nfr.id) not in traced:
            r.error(nfr.id, "NFR not covered by any requirement")
    for c in spec.conflicts:
        r.error("conflict", f"{c.between}: {c.question}")
    return r


def validate_plan(plan: TaskPlan, spec: SpecPackage) -> Report:
    r = Report()
    req_names = {_norm(q.name) for c in spec.capabilities for q in c.requirements}
    scenarios = [s.name for c in spec.capabilities for q in c.requirements for s in q.scenarios]
    covered = {_norm(n) for g in plan.groups for t in g.tasks for n in t.requirements}
    for c in spec.capabilities:
        for q in c.requirements:
            if _norm(q.name) not in covered:
                r.error(q.name, "Requirement has no task")
    for unknown in sorted(covered - req_names):
        r.warn("tasks", f"Task refers to unknown requirement '{unknown}'")
    planned = {_norm(t.scenario) for t in plan.qa_plan}
    for s in scenarios:
        if _norm(s) not in planned:
            r.error(s, "Scenario has no test in the QA plan")
    return r


def harness_test_ids(tests: str) -> set[str]:
    return set(HARNESS_CALL.findall(tests))


def harness_test_names(tests: str) -> list[str]:
    return [m[1] for m in TEST_NAME.findall(tests)]


def static_checks(html: str, tests: str, plan: TaskPlan) -> Report:
    r = Report()
    low = html.lower()
    if "<html" not in low or "</html>" not in low:
        r.error("app", "Not a complete HTML document")
    if "__resetapp" not in low:
        r.error("app", "Missing window.__resetApp, so tests cannot start from a clean state")
    for pattern, msg in EXTERNAL:
        if pattern.search(html):
            r.error("app", f"App {msg}; it must be self contained")
    for tid in sorted(harness_test_ids(tests)):
        if not re.search(rf"['\"`]{re.escape(tid)}['\"`]", html):
            r.error("tests vs app", f"Test id '{tid}' is used by the tests but not found in the app")
    names = {_norm(n) for n in harness_test_names(tests)}
    for t in plan.qa_plan:
        if _norm(t.scenario) not in names and _norm(t.test_name) not in names:
            r.error("tests", f"No automated test for scenario '{t.scenario}'")
    return r


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def near_duplicates(labels: list[str], vectors: list[list[float]], threshold: float = 0.93) -> list[tuple[str, str, float]]:
    pairs = []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            sim = cosine(vectors[i], vectors[j])
            if sim >= threshold:
                pairs.append((labels[i], labels[j], round(sim, 3)))
    return pairs
