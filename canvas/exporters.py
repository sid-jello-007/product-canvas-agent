"""Render artefacts in the formats teams already use.

- OpenSpec: openspec/changes/<change-id>/ with proposal.md, specs/<capability>/spec.md,
  design.md and tasks.md, plus explore.md. Drop the folder into a repo and any
  OpenSpec-aware coding agent can pick it up.
- Architecture: a CALM style JSON model plus readable decisions.
- Jira: CSV import with epics linked to feature stories.
- The live app, its tests and the QA report.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile

from .schemas import (
    Architecture, DesignDoc, Exploration, ProductCanvas, QAReview, SpecPackage, TaskPlan,
)


def _bullets(items, empty="- (none)"):
    return "\n".join(f"- {i}" for i in items) or empty


# ---------------- 01 Domain store ----------------

def canvas_md(c: ProductCanvas) -> str:
    epics = []
    for i, e in enumerate(c.epics, 1):
        epics.append(f"### Epic {i}: {e.title}\n*Outcome: {e.outcome}*\n")
        for f in e.features:
            epics.append(
                f"**Feature: {f.title}**. {f.description}\n\n"
                f"Acceptance criteria:\n{_bullets(f.acceptance_criteria)}\n\n"
                f"Test scenarios:\n{_bullets(f.test_scenarios)}\n"
            )
    metrics = "\n".join(f"- **{m.name}**: {m.target}" for m in c.success_metrics)
    questions = _bullets(c.clarifying_questions, "- None")
    return f"""## {c.product_name}
`change: {c.change_id}`

**Problem.** {c.problem}

**Users.** {", ".join(c.target_users)}

**Value proposition.** {c.value_proposition}

{chr(10).join(epics)}
### Success metrics
{metrics}

### Out of scope
{_bullets(c.out_of_scope)}

### Assumptions
{_bullets(c.assumptions)}

### Clarifying questions for the product owner
{questions}
"""


def architecture_md(a: Architecture) -> str:
    nodes = "\n".join(f"| `{n.unique_id}` | {n.node_type} | {n.name} | {n.description} |" for n in a.nodes)
    rels = "\n".join(f"| `{r.source}` → `{r.destination}` | {r.protocol} | {r.description} |" for r in a.relationships)
    decisions = "\n".join(f"- **{d.title}**: {d.decision} *({d.rationale})*" for d in a.decisions)
    nfrs = "\n".join(f"- **{n.id}** ({n.category}): {n.statement}" for n in a.nfrs)
    ifaces = "\n".join(f"- **{i.name}** ({i.kind}): {i.description}" for i in a.interfaces)
    return f"""**Intent.** {a.intent}

**Patterns.** {", ".join(a.patterns)}

### Nodes
| id | type | name | description |
|---|---|---|---|
{nodes}

### Relationships
| from → to | protocol | description |
|---|---|---|
{rels}

### Decisions
{decisions}

### NFRs
{nfrs}

### Controls
{_bullets(a.controls)}

### Interfaces
{ifaces}
"""


def calm_json(a: Architecture, change_id: str) -> str:
    """A model in the shape of FINOS CALM (nodes, relationships, metadata). Illustrative, not schema validated."""
    doc = {
        "$schema": "https://calm.finos.org/release/1.0/meta/calm.json",
        "unique-id": change_id,
        "name": change_id,
        "nodes": [
            {"unique-id": n.unique_id, "node-type": n.node_type, "name": n.name, "description": n.description}
            for n in a.nodes
        ],
        "relationships": [
            {"unique-id": r.unique_id, "description": r.description, "protocol": r.protocol,
             "relationship-type": {"connects": {"source": {"node": r.source}, "destination": {"node": r.destination}}}}
            for r in a.relationships
        ],
        "metadata": [{"decisions": [d.model_dump() for d in a.decisions]}, {"nfrs": [n.model_dump() for n in a.nfrs]},
                     {"controls": a.controls}],
    }
    return json.dumps(doc, indent=2)


def proposal_md(spec: SpecPackage) -> str:
    caps = "\n".join(f"- `{c.name}`: {c.purpose}" for c in spec.capabilities)
    return f"""## Why
{spec.proposal.why}

## What Changes
{_bullets(spec.proposal.what_changes)}

## Capabilities

### New Capabilities
{caps}

### Modified Capabilities
- None

## Impact
{spec.proposal.impact}
"""


def capability_spec_md(cap) -> str:
    """One OpenSpec delta spec: ADDED requirements with WHEN/THEN scenarios."""
    out = ["## ADDED Requirements", ""]
    for req in cap.requirements:
        out += [f"### Requirement: {req.name}", req.statement, ""]
        for sc in req.scenarios:
            out.append(f"#### Scenario: {sc.name}")
            if sc.given.strip():
                out.append(f"- **GIVEN** {sc.given}")
            out += [f"- **WHEN** {sc.when}", f"- **THEN** {sc.then}", ""]
    return "\n".join(out)


def spec_preview_md(spec: SpecPackage) -> str:
    parts = ["# proposal.md", proposal_md(spec)]
    for c in spec.capabilities:
        parts += [f"# specs/{c.name}/spec.md", f"*{c.purpose}*\n", capability_spec_md(c)]
    if spec.conflicts:
        parts.append("# Conflicts raised by the spec agent")
        parts += [f"- **{c.between}**: {c.description}\n  - **Question:** {c.question}" for c in spec.conflicts]
    return "\n".join(parts)


# ---------------- 02 Delivery ----------------

def explore_md(x: Exploration) -> str:
    return f"""## Target
{x.target_summary}

## Baseline findings
{_bullets(x.baseline_findings)}

## Implementation delta
{_bullets(x.implementation_delta)}

## Risks
{_bullets(x.risks)}
"""


def design_md(d: DesignDoc) -> str:
    decisions = "\n".join(f"- **{x.title}**: {x.decision} *({x.rationale})*" for x in d.decisions)
    return f"""## Context
{d.context}

## Goals / Non-Goals
**Goals**
{_bullets(d.goals)}

**Non-Goals**
{_bullets(d.non_goals)}

## Decisions
{decisions}

## UI structure
{_bullets(d.ui_structure)}

## State and data
{d.state_and_data}

## Test strategy
{d.test_strategy}

## Risks / Trade-offs
{_bullets(d.risks_and_tradeoffs)}
"""


def tasks_md(p: TaskPlan) -> str:
    out = []
    for g in p.groups:
        out.append(f"## {g.number}. {g.title}")
        out += [f"- [ ] {t.id} {t.description}" for t in g.tasks]
        out.append("")
    return "\n".join(out)


def qa_plan_md(p: TaskPlan) -> str:
    return "\n".join(
        f"**{t.scenario}** → `{t.test_name}`\n" + "\n".join(f"  {i}. {s}" for i, s in enumerate(t.steps, 1))
        for t in p.qa_plan
    )


def qa_report_md(review: QAReview, static_md: str, rounds: list[str]) -> str:
    rows = "\n".join(
        f"| {'✅' if r.status == 'pass' else '❌'} | {r.scenario} | {r.owner if r.status == 'fail' else ''} | {r.evidence} |"
        for r in review.results
    )
    passed = sum(r.status == "pass" for r in review.results)
    history = _bullets(rounds, "- Built once, no fixes needed")
    return f"""### Independent QA review: {passed}/{len(review.results)} scenarios pass
| | Scenario | Owner | Evidence |
|---|---|---|---|
{rows}

{review.summary}

### Static checks
{static_md}

### Build history
{history}
"""


def jira_csv(c: ProductCanvas) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Issue Id", "Parent Id", "Issue Type", "Summary", "Description", "Labels"])
    n = 1
    for e in c.epics:
        epic_id = n
        w.writerow([epic_id, "", "Epic", e.title, e.outcome, c.change_id])
        n += 1
        for f in e.features:
            desc = f.description + "\n\nAcceptance criteria:\n" + "\n".join(f"* {a}" for a in f.acceptance_criteria)
            desc += "\n\nTest scenarios:\n" + "\n".join(f"* {s}" for s in f.test_scenarios)
            w.writerow([n, epic_id, "Story", f.title, desc, c.change_id])
            n += 1
    return out.getvalue()


def package_zip(path: str, canvas: ProductCanvas, arch: Architecture, spec: SpecPackage,
                explore: Exploration | None = None, design: DesignDoc | None = None, plan: TaskPlan | None = None,
                app_html: str = "", tests_js: str = "", qa_md: str = "") -> str:
    """Write the whole change as a zip laid out the way a repo would hold it."""
    base = f"openspec/changes/{canvas.change_id}"
    files = {
        "product/canvas.md": "# Product canvas\n" + canvas_md(canvas),
        "product/jira_import.csv": jira_csv(canvas),
        "architecture/architecture.md": "# Architecture\n" + architecture_md(arch),
        "architecture/calm.json": calm_json(arch, canvas.change_id),
        f"{base}/proposal.md": f"# {canvas.change_id}\n\n" + proposal_md(spec),
    }
    for cap in spec.capabilities:
        files[f"{base}/specs/{cap.name}/spec.md"] = capability_spec_md(cap)
    if explore:
        files[f"{base}/explore.md"] = "# Explore\n" + explore_md(explore)
    if design:
        files[f"{base}/design.md"] = "# Design\n" + design_md(design)
    if plan:
        files[f"{base}/tasks.md"] = "# Tasks\n\n" + tasks_md(plan)
        files["qa/qa_plan.md"] = "# QA plan\n\n" + qa_plan_md(plan)
    if app_html:
        files["app/index.html"] = app_html
    if tests_js:
        files["app/tests.js"] = tests_js
    if qa_md:
        files["qa/report.md"] = "# QA report\n\n" + qa_md
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(f"{canvas.change_id}/{name}", content)
    return path
