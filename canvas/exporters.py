"""Hand off to the customer's existing tools: Jira CSV, markdown for Confluence or Notion, raw JSON."""
from __future__ import annotations

import csv
import io

from .schemas import ProductCanvas, ProductSpec, TicketPlan


def jira_csv(plan: TicketPlan) -> str:
    """CSV in the shape Jira's importer understands, with Issue Id / Parent Id linking stories to epics."""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Issue Id", "Parent Id", "Issue Type", "Summary", "Description", "Priority", "Story Points", "Labels"])
    next_id = 1
    for epic in plan.epics:
        epic_id = next_id
        w.writerow([epic_id, "", "Epic", f"{epic.key}: {epic.title}", epic.summary, "", "", ""])
        next_id += 1
        for s in epic.stories:
            desc = s.user_story + "\n\nAcceptance criteria:\n" + "\n".join(f"* {ac}" for ac in s.acceptance_criteria)
            if s.dependencies:
                desc += "\n\nDepends on: " + ", ".join(s.dependencies)
            if s.requirement_ids:
                desc += "\nRequirements: " + ", ".join(s.requirement_ids)
            w.writerow([next_id, epic_id, "Story", f"{s.key}: {s.title}", desc, s.priority, s.story_points, " ".join(s.labels)])
            next_id += 1
    return out.getvalue()


def canvas_markdown(c: ProductCanvas) -> str:
    def bullets(items):
        return "\n".join(f"- {i}" for i in items) or "- (none)"

    users = "\n".join(f"- **{p.name}**: {p.needs}" for p in c.target_users)
    metrics = "\n".join(f"- **{m.name}**: {m.target} ({m.why})" for m in c.success_metrics)
    return f"""## {c.product_name}
*{c.one_line_pitch}*

**Problem.** {c.problem}

**Value proposition.** {c.value_proposition}

### Target users
{users}

### Jobs to be done
{bullets(c.jobs_to_be_done)}

### Key features
{bullets(c.key_features)}

### Success metrics
{metrics}

### Assumptions and risks
{bullets(c.assumptions_and_risks)}

### Out of scope
{bullets(c.out_of_scope)}

### Open questions
{bullets(c.open_questions)}
"""


def spec_markdown(s: ProductSpec) -> str:
    reqs = "\n".join(f"| {r.id} | {r.title} | {r.description} | {r.priority} |" for r in s.requirements)
    return f"""## Overview
{s.overview}

### Goals
{chr(10).join(f'- {g}' for g in s.goals)}

### Non goals
{chr(10).join(f'- {g}' for g in s.non_goals)}

### Functional requirements
| ID | Title | Description | Priority |
|---|---|---|---|
{reqs}

### Non functional requirements
{chr(10).join(f'- {n}' for n in s.non_functional_requirements)}

### User flows
{chr(10).join(f'{i}. {f}' for i, f in enumerate(s.user_flows, 1))}
"""


def tickets_markdown(plan: TicketPlan) -> str:
    parts = []
    for e in plan.epics:
        parts.append(f"## {e.key}: {e.title}\n{e.summary}\n")
        for s in e.stories:
            ac = "\n".join(f"  - {a}" for a in s.acceptance_criteria)
            deps = f" | depends on {', '.join(s.dependencies)}" if s.dependencies else ""
            parts.append(
                f"**{s.key}: {s.title}** ({s.story_points} pts, {s.priority}, {', '.join(s.requirement_ids) or 'no requirement'}{deps})\n"
                f"{s.user_story}\n{ac}\n"
            )
    return "\n".join(parts)


def ticket_rows(plan: TicketPlan) -> list[list]:
    return [
        [e.key, s.key, s.title, s.story_points, s.priority, ", ".join(s.requirement_ids), ", ".join(s.dependencies)]
        for e in plan.epics for s in e.stories
    ]
