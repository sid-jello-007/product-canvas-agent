"""Offline tests: the whole workflow runs against FakeLLM, so CI never needs an API key."""
import csv
import io
from pathlib import Path

import pytest

from canvas import exporters
from canvas.config import Limits
from canvas.evals import find_duplicates, story_issues
from canvas.guardrails import GuardrailError, apply_moderation, check_inputs
from canvas.ingest import build_context, docx_to_text, html_to_text
from canvas.llm import FakeLLM
from canvas.pipeline import build_backlog, build_canvas
from canvas.schemas import Story

EXAMPLES = Path(__file__).parent.parent / "examples"


def make_story(**overrides):
    base = dict(
        key="E1-S1", title="t", user_story="As a user, I want a thing, so that I benefit.",
        acceptance_criteria=["Given a, when b, then c.", "Given d, when e, then f."],
        story_points=3, priority="High", requirement_ids=["FR-1"], labels=[], dependencies=[],
    )
    base.update(overrides)
    return Story(**base)


# ---------- evals ----------

def test_good_story_passes_rules():
    assert story_issues(make_story(), {"FR-1"}) == []


@pytest.mark.parametrize("override, expected", [
    ({"user_story": "Balances screen."}, "not in 'As a"),
    ({"acceptance_criteria": ["Given a, when b, then c."]}, "at least 2"),
    ({"acceptance_criteria": ["Shows balances.", "Works."]}, "Given..., when"),
    ({"story_points": 4}, "Fibonacci"),
    ({"story_points": 13}, "too large"),
    ({"requirement_ids": []}, "Not linked"),
    ({"requirement_ids": ["FR-9"]}, "unknown requirements"),
])
def test_rule_failures(override, expected):
    issues = story_issues(make_story(**override), {"FR-1"})
    assert any(expected in i for i in issues), issues


def test_duplicates_found():
    stories = [make_story(key="A"), make_story(key="B"), make_story(key="C")]
    vectors = [[1, 0], [0.99, 0.05], [0, 1]]
    assert find_duplicates(stories, vectors, 0.95) == [("A", "B", 0.999)]


# ---------- guardrails ----------

def test_guardrails_reject_empty_and_bad_files(tmp_path):
    with pytest.raises(GuardrailError):
        check_inputs("", [], Limits())
    bad = tmp_path / "virus.exe"
    bad.write_bytes(b"x")
    with pytest.raises(GuardrailError):
        check_inputs("idea", [str(bad)], Limits())


def test_moderation_blocks_harmful_and_warns_on_pii():
    with pytest.raises(GuardrailError):
        apply_moderation(["violence_and_threats"])
    assert apply_moderation(["pii"]) and apply_moderation([]) == []


# ---------- ingest ----------

def test_html_prototype_keeps_product_signals():
    text = html_to_text((EXAMPLES / "prototype_savings_pots.html").read_text())
    assert "# Your pots" in text and "[button] Create a new pot" in text and "[input] e.g. New laptop" in text
    assert "font-family" not in text


def test_docx_parsing():
    from docx import Document
    doc = Document()
    doc.add_paragraph("Brief: loyalty app")
    buf = io.BytesIO()
    doc.save(buf)
    assert "loyalty app" in docx_to_text(buf.getvalue())


def test_context_budget_truncates():
    ctx = build_context("x" * 500, [], FakeLLM(), max_chars=100)
    assert ctx.truncated and len(ctx.sources[0].text) == 100
    assert '<source name="idea"' in ctx.as_prompt()


# ---------- end to end ----------

def test_full_workflow_refines_weak_story_and_exports():
    llm = FakeLLM()
    c = build_canvas("Split bills with flatmates", [str(EXAMPLES / "brief_merchant_onboarding.md")], llm)
    assert c.canvas.product_name
    r = build_backlog(c.canvas, c.context.as_prompt(), llm)

    # The demo backlog has one weak story; the loop should fix it and lift the score.
    assert r.quality.refined_keys == ["E2-S2"]
    assert r.quality.overall > r.first_pass_score
    assert r.quality.failing_keys(3.5) == []
    assert r.quality.uncovered_requirements == []

    rows = list(csv.DictReader(io.StringIO(exporters.jira_csv(r.plan))))
    assert {row["Issue Type"] for row in rows} == {"Epic", "Story"}
    stories = [row for row in rows if row["Issue Type"] == "Story"]
    assert all(row["Parent Id"] for row in stories)

    steps = [e.step for e in llm.telemetry.events]
    assert steps[0] == "guardrail: moderation" and "agent: refine" in steps
    assert r.kpis["stories"] == 5
