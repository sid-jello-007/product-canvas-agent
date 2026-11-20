"""Quality checks on the backlog. This is how we know the output is usable.

Two kinds of evaluation, combined into one score:
- Deterministic checks: rules a script can verify every time (format,
  Fibonacci points, every requirement covered). Cheap, exact, no model.
- Model based checks: an LLM judge scores each story on INVEST, and
  embeddings flag near duplicate stories. Catch what rules cannot.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .schemas import Critique, ProductSpec, Story, TicketPlan

FIBONACCI = {1, 2, 3, 5, 8, 13}
USER_STORY_RE = re.compile(r"^as an? .+?,? i want .+?,? so that .+", re.IGNORECASE | re.DOTALL)
GWT_RE = re.compile(r"^given .+?,? when .+?,? then .+", re.IGNORECASE | re.DOTALL)


def story_issues(story: Story, valid_req_ids: set[str]) -> list[str]:
    """Rule based problems for one story (empty list means it passes)."""
    issues = []
    if not USER_STORY_RE.match(story.user_story.strip()):
        issues.append("User story is not in 'As a..., I want..., so that...' form")
    if len(story.acceptance_criteria) < 2:
        issues.append("Needs at least 2 acceptance criteria")
    bad_ac = [ac for ac in story.acceptance_criteria if not GWT_RE.match(ac.strip())]
    if bad_ac:
        issues.append(f"{len(bad_ac)} acceptance criteria not in 'Given..., when..., then...' form")
    if story.story_points not in FIBONACCI:
        issues.append(f"Story points {story.story_points} is not a Fibonacci number")
    elif story.story_points > 8:
        issues.append("13 points is too large; split the story")
    if not story.requirement_ids:
        issues.append("Not linked to any spec requirement")
    elif set(story.requirement_ids) - valid_req_ids:
        issues.append(f"Links to unknown requirements {sorted(set(story.requirement_ids) - valid_req_ids)}")
    return issues


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def find_duplicates(stories: list[Story], vectors: list[list[float]], threshold: float) -> list[tuple[str, str, float]]:
    pairs = []
    for i in range(len(stories)):
        for j in range(i + 1, len(stories)):
            sim = cosine(vectors[i], vectors[j])
            if sim >= threshold:
                pairs.append((stories[i].key, stories[j].key, round(sim, 3)))
    return pairs


@dataclass
class QualityReport:
    rule_issues: dict[str, list[str]]
    judge_scores: dict[str, int]
    judge_issues: dict[str, list[str]]
    judge_comment: str
    uncovered_requirements: list[str]
    duplicates: list[tuple[str, str, float]] = field(default_factory=list)
    refined_keys: list[str] = field(default_factory=list)

    @property
    def stories_total(self) -> int:
        return len(self.rule_issues)

    @property
    def rule_pass_rate(self) -> float:
        if not self.rule_issues:
            return 0.0
        return sum(1 for v in self.rule_issues.values() if not v) / len(self.rule_issues)

    @property
    def avg_judge_score(self) -> float:
        return sum(self.judge_scores.values()) / len(self.judge_scores) if self.judge_scores else 0.0

    @property
    def overall(self) -> int:
        """0 to 100: half rules, a third judge, the rest coverage, minus a penalty per duplicate."""
        coverage = 1.0 if not self.uncovered_requirements else max(0.0, 1 - 0.2 * len(self.uncovered_requirements))
        score = 50 * self.rule_pass_rate + 35 * (self.avg_judge_score / 5) + 15 * coverage
        return max(0, round(score - 5 * len(self.duplicates)))

    def failing_keys(self, pass_score: float) -> list[str]:
        return [
            k for k in self.rule_issues
            if self.rule_issues[k] or self.judge_scores.get(k, 5) < pass_score
        ]

    def combined_issues(self) -> dict[str, list[str]]:
        return {k: self.rule_issues.get(k, []) + self.judge_issues.get(k, []) for k in self.rule_issues}


def evaluate(plan: TicketPlan, spec: ProductSpec, critique: Critique) -> QualityReport:
    valid_ids = {r.id for r in spec.requirements}
    stories = plan.all_stories()
    covered = {rid for s in stories for rid in s.requirement_ids}
    must_should = [r.id for r in spec.requirements if r.priority in ("Must", "Should")]
    return QualityReport(
        rule_issues={s.key: story_issues(s, valid_ids) for s in stories},
        judge_scores={r.key: r.score for r in critique.reviews},
        judge_issues={r.key: r.issues for r in critique.reviews},
        judge_comment=critique.overall_comment,
        uncovered_requirements=[rid for rid in must_should if rid not in covered],
    )
