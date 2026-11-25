"""Offline tests: every stage runs against FakeLLM, so CI never needs an API key."""
import io
import zipfile
from pathlib import Path

import pytest

from canvas import demo, exporters
from canvas.agents import extract_code, skill
from canvas.config import Limits
from canvas.evals import static_checks, validate_canvas, validate_plan, validate_spec
from canvas.guardrails import GuardrailError, apply_moderation, check_inputs
from canvas.harness import inject_tests, preview_iframe
from canvas.ingest import build_context, docx_to_text, html_to_text
from canvas.llm import FakeLLM
from canvas.pipeline import fast_forward, stage_build, stage_canvas, stage_design, stage_inputs, stage_plan, stage_spec
from canvas.schemas import Architecture, Conflict, ProductCanvas, SpecPackage, TaskPlan

EXAMPLES = Path(__file__).parent.parent / "examples"
CANVAS = ProductCanvas.model_validate(demo.CANVAS)
ARCH = Architecture.model_validate(demo.ARCH)
SPEC = SpecPackage.model_validate(demo.SPEC)
PLAN = TaskPlan.model_validate(demo.PLAN)


# ---------- OpenSpec validation and traceability ----------

def test_demo_artefacts_are_valid():
    assert validate_canvas(CANVAS).ok
    assert validate_spec(SPEC, CANVAS, ARCH).ok
    assert validate_plan(PLAN, SPEC).ok


def test_spec_rules_catch_problems():
    bad = SPEC.model_copy(deep=True)
    req = bad.capabilities[0].requirements[0]
    req.statement = "Users can create pots."          # no SHALL or MUST
    req.scenarios[0].then = ""                         # scenario without THEN
    bad.capabilities[0].name = "Pot Management"        # not kebab-case
    bad.capabilities[2].requirements = bad.capabilities[2].requirements[1:]  # drops NFR-1 coverage
    messages = " | ".join(f.message for f in validate_spec(bad, CANVAS, ARCH).errors)
    for expected in ["SHALL or MUST", "WHEN and THEN", "kebab-case", "NFR not covered"]:
        assert expected in messages


def test_conflicts_block_approval():
    conflicted = SPEC.model_copy(deep=True)
    conflicted.conflicts = [Conflict(between="Add money vs NFR-2", description="x", question="Which wins?")]
    assert not validate_spec(conflicted, CANVAS, ARCH).ok


def test_uncovered_feature_and_missing_task_are_errors():
    spec = SPEC.model_copy(deep=True)
    spec.capabilities[1].requirements[0].traces_to = []
    assert any("See progress" in f.where for f in validate_spec(spec, CANVAS, ARCH).errors)
    plan = PLAN.model_copy(deep=True)
    plan.groups[1].tasks = plan.groups[1].tasks[1:]
    assert any(f.where == "Show progress" for f in validate_plan(plan, SPEC).errors)


# ---------- static build checks ----------

def test_static_checks_pass_on_demo_build():
    assert static_checks(demo.APP_V2, demo.TESTS, PLAN).ok


def test_static_checks_catch_external_calls_missing_ids_and_reset():
    html = demo.APP_V2.replace("window.__resetApp", "window.reset").replace(
        "</head>", '<script src="https://cdn.example.com/x.js"></script></head>')
    tests = demo.TESTS + '\ntest("Extra", async () => { click("ghost-button"); });'
    messages = " | ".join(f.message for f in static_checks(html, tests, PLAN).errors)
    assert "__resetApp" in messages and "external script" in messages and "ghost-button" in messages


# ---------- harness, skills, parsing ----------

def test_harness_is_injected_before_body_end():
    out = inject_tests(demo.APP_V2, demo.TESTS)
    assert out.index("window.__runTests") < out.lower().rindex("</body>")
    assert 'srcdoc="' in preview_iframe(demo.APP_V2, demo.TESTS) and "<script>" not in preview_iframe(demo.APP_V2)


def test_every_agent_has_a_skill_file():
    for name in ["product-canvas", "architecture", "spec-author", "explore", "design", "task-planner",
                 "qa-automation", "implementation", "qa-review"]:
        text = skill(name)
        assert "---" not in text.splitlines()[0] and "<source>" in text


def test_extract_code():
    assert extract_code("Here:\n```html\n<html></html>\n```\nDone", "html") == "<html></html>"
    assert extract_code("no fence", "html") == "no fence"


# ---------- guardrails and ingest ----------

def test_guardrails(tmp_path):
    with pytest.raises(GuardrailError):
        check_inputs("", [], Limits())
    bad = tmp_path / "virus.exe"
    bad.write_bytes(b"x")
    with pytest.raises(GuardrailError):
        check_inputs("idea", [str(bad)], Limits())
    with pytest.raises(GuardrailError):
        apply_moderation(["violence_and_threats"])
    assert apply_moderation(["pii"]) and apply_moderation([]) == []


def test_ingest_html_docx_and_budget():
    text = html_to_text((EXAMPLES / "prototype_savings_pots.html").read_text())
    assert "# Your pots" in text and "[button] Create a new pot" in text
    from docx import Document
    d = Document()
    d.add_paragraph("Brief: loyalty app")
    buf = io.BytesIO()
    d.save(buf)
    assert "loyalty app" in docx_to_text(buf.getvalue())
    ctx = build_context("x" * 500, [], FakeLLM(), max_chars=100)
    assert ctx.truncated and '<source name="idea"' in ctx.as_prompt()


# ---------- end to end ----------

def test_target_code_is_withheld_until_explore():
    llm = FakeLLM()
    run = stage_inputs("Savings pots", [], "", [], str(EXAMPLES / "prototype_savings_pots.html"), llm)
    assert "Your pots" in run.target_code and "Your pots" not in run.po_context
    run = stage_spec(stage_canvas(run, llm), llm)
    assert "explore" not in " ".join(e.step for e in llm.telemetry.events)


def test_full_flow_red_green_fix_and_package(tmp_path):
    llm = FakeLLM()
    run = stage_inputs("Savings pots", [], "No data leaves the device", [], None, llm)
    for stage in (stage_canvas, stage_spec, stage_design, stage_plan):
        run = stage(run, llm)
    assert run.tests.count("test(") == 7
    run = stage_build(run, llm)

    # First build fails one scenario, QA triages it to the app, the fix round turns it green.
    assert run.build_rounds == ["Round 1: 6/7 scenarios pass", "Round 2: 7/7 scenarios pass"]
    assert all(r.status == "pass" for r in run.review.results) and run.static_report.ok
    steps = [e.step for e in llm.telemetry.events]
    assert steps.index("QA automation agent (tests first)") < steps.index("implementation agent (build)")
    assert "implementation agent (fix)" in steps

    path = exporters.package_zip(str(tmp_path / "p.zip"), run.canvas, run.arch, run.spec, run.explore,
                                 run.design, run.plan, run.html, run.tests, "report")
    names = zipfile.ZipFile(path).namelist()
    base = "add-savings-pots/openspec/changes/add-savings-pots/"
    for f in ["proposal.md", "design.md", "tasks.md", "explore.md", "specs/pot-management/spec.md"]:
        assert base + f in names
    assert "add-savings-pots/app/index.html" in names and "add-savings-pots/architecture/calm.json" in names
    spec_md = zipfile.ZipFile(path).read(base + "specs/pot-management/spec.md").decode()
    assert spec_md.startswith("## ADDED Requirements") and "#### Scenario:" in spec_md and "- **WHEN**" in spec_md


def test_fast_forward():
    run = fast_forward("Savings pots", [], "", [], None, FakeLLM())
    assert run.html and run.approvals
