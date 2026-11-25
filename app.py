"""Product Canvas: idea to live, tested prototype through an OpenSpec change, on Mistral.

Gradio app deployed as a Hugging Face Space. Every stage stops at a checkpoint
(C0 to C4) for a human to approve; fast-forward runs them all. The spec stage
is also exposed as an MCP tool so it can be called from Le Chat or Claude.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import gradio as gr

from canvas import exporters as ex
from canvas.config import SETTINGS
from canvas.evals import validate_canvas
from canvas.guardrails import GuardrailError
from canvas.harness import preview_iframe
from canvas.llm import make_llm, to_json
from canvas.pipeline import (
    Run, fast_forward, stage_build, stage_canvas, stage_design, stage_inputs, stage_plan, stage_spec, value_kpis,
)
from canvas.schemas import Architecture, ProductCanvas

EXAMPLES = Path(__file__).parent / "examples"
_, DEMO = make_llm()

INTRO = """# Product Canvas
**One idea in. An approved OpenSpec change and a live, tested prototype out.**

`PO + architecture inputs` → **canvas** → C0 → **shared spec** → C1 → **explore + design** → C2 → **tasks + tests first** → C3 → **build, QA, fix** → C4 → **package**
"""
DEMO_BANNER = "> **Demo mode:** no `MISTRAL_API_KEY` is set, so every stage returns a sample run (Savings Pots) and no model is called."


def _llm(run: Run | None):
    return make_llm(run.telemetry if run else None)[0]


def _paths(files) -> list[str]:
    if not files:
        return []
    files = files if isinstance(files, list) else [files]
    return [f if isinstance(f, str) else f.name for f in files]


def _fail(exc: Exception):
    if isinstance(exc, gr.Error):
        raise exc
    if isinstance(exc, GuardrailError):
        raise gr.Error(str(exc))
    raise gr.Error(f"Something went wrong: {exc}")


def _need(run: Run | None, attr: str, msg: str) -> Run:
    if not run or getattr(run, attr) in (None, ""):
        raise gr.Error(msg)
    return run


# ---------------- rendering ----------------

def render(run: Run | None, tab: str, status: str = "", downloads=None):
    """Every handler returns the full set of outputs, so the UI always reflects the run."""
    r = run or Run()
    questions = (
        "\n".join(f"{i}. {q}" for i, q in enumerate(r.canvas.clarifying_questions, 1))
        if r.canvas and r.canvas.clarifying_questions else "No open questions."
    )
    t = r.telemetry.totals()
    value = ""
    if r.canvas:
        k = value_kpis(r)
        value = f"""### Value of this run
| Measure | Value |
|---|---|
| Requirements in the shared spec | {k['requirements']} |
| Scenarios passing in the live build | {k['scenarios_passing']} |
| Manual effort replaced (estimate) | {k['manual_hours_estimate']:g} hours, about £{k['manual_cost_gbp']:,} |
| Time and calls | {t['seconds']} s across {t['calls']} model calls |
| Model cost (estimate) | ${t['cost_usd']:.4f} ({t['input_tokens']:,} input, {t['output_tokens']:,} output tokens) |

*Assumptions: {k['assumptions']}. Prices are indicative, see `canvas/config.py`.*
"""
    approvals = "\n".join(f"- {a}" for a in r.approvals) or "No checkpoints approved yet."
    return [
        r,
        gr.update(selected=tab),
        status,
        ex.canvas_md(r.canvas) if r.canvas else "",
        ex.architecture_md(r.arch) if r.arch else "",
        r.canvas_report.markdown("Canvas checks") if r.canvas else "",
        questions,
        to_json(r.canvas) if r.canvas else "",
        to_json(r.arch) if r.arch else "",
        ex.spec_preview_md(r.spec) if r.spec else "",
        r.spec_report.markdown("OpenSpec validation and traceability") if r.spec else "",
        ex.explore_md(r.explore) if r.explore else "",
        ex.design_md(r.design) if r.design else "",
        ex.tasks_md(r.plan) if r.plan else "",
        ex.qa_plan_md(r.plan) if r.plan else "",
        r.plan_report.markdown("Plan coverage") if r.plan else "",
        r.tests or "",
        preview_iframe(r.html, r.tests) if r.html else "<p>Approve C3 to build the app.</p>",
        ex.qa_report_md(r.review, r.static_report.markdown("Static checks"), r.build_rounds) if r.review else "",
        r.html or "",
        value,
        r.telemetry.rows(),
        downloads,
        approvals,
        gr.update(interactive=r.canvas is not None),
        gr.update(interactive=r.spec is not None),
        gr.update(interactive=r.design is not None),
        gr.update(interactive=r.plan is not None),
        gr.update(interactive=bool(r.html)),
    ]


def _package(run: Run) -> list[str]:
    out = Path(tempfile.mkdtemp())
    qa = ex.qa_report_md(run.review, run.static_report.markdown("Static checks"), run.build_rounds) if run.review else ""
    zpath = ex.package_zip(str(out / f"{run.canvas.change_id}.zip"), run.canvas, run.arch, run.spec,
                           run.explore, run.design, run.plan, run.html, run.tests, qa)
    files = [zpath]
    if run.html:
        (out / "index.html").write_text(run.html, encoding="utf-8")
        files.append(str(out / "index.html"))
    return files


# ---------------- handlers (one per checkpoint) ----------------

def on_start(idea, po_files, arch_text, arch_files, target_file):
    llm = _llm(None)
    try:
        run = stage_inputs(idea or "", _paths(po_files), arch_text or "", _paths(arch_files),
                           (_paths(target_file) or [None])[0], llm)
        run = stage_canvas(run, llm)
    except Exception as exc:  # noqa: BLE001
        _fail(exc)
    warn = "".join(f"\n> ⚠️ {w}" for w in run.warnings)
    return render(run, "canvas", f"**Read:** {run.sources_summary}{warn}\n\n"
                                 "**C0:** review the canvas and architecture, answer any questions, then approve.")


def on_redraft(run, answers):
    run = _need(run, "canvas", "Start from the Inputs tab first.")
    try:
        run = stage_canvas(run, _llm(run), answers or "")
    except Exception as exc:  # noqa: BLE001
        _fail(exc)
    return render(run, "canvas", "Canvas and architecture redrafted with your answers.")


def on_c0(run, canvas_json, arch_json):
    run = _need(run, "canvas", "Draft a canvas first.")
    try:
        run.canvas = ProductCanvas.model_validate_json(canvas_json)
        run.arch = Architecture.model_validate_json(arch_json)
    except Exception as exc:  # noqa: BLE001
        raise gr.Error(f"Edited JSON does not match the schema: {exc}") from exc
    run.canvas_report = validate_canvas(run.canvas)
    if not run.canvas_report.ok:
        raise gr.Error("Fix the canvas errors before approving.")
    run.approvals.append("C0: product canvas and architecture approved")
    try:
        run = stage_spec(run, _llm(run))
    except Exception as exc:  # noqa: BLE001
        _fail(exc)
    msg = "**C1:** review the shared spec."
    if run.spec.conflicts:
        msg += " Conflicts were raised: answer them below and re-run the spec."
    return render(run, "spec", msg)


def on_respec(run, resolutions):
    run = _need(run, "spec", "Approve C0 first.")
    try:
        run = stage_spec(run, _llm(run), resolutions or "")
    except Exception as exc:  # noqa: BLE001
        _fail(exc)
    return render(run, "spec", "Spec re-run with your answers.")


def on_c1(run, override):
    run = _need(run, "spec", "Approve C0 first.")
    if not run.spec_report.ok and not override:
        raise gr.Error("The spec has validation errors or open conflicts. Resolve them, or tick 'approve with known issues'.")
    run.approvals.append("C1: shared spec approved" + ("" if run.spec_report.ok else " with known issues"))
    try:
        run = stage_design(run, _llm(run))
    except Exception as exc:  # noqa: BLE001
        _fail(exc)
    return render(run, "design", "**C2:** Explore was the first access to target code. Review the design, then approve.")


def on_c2(run):
    run = _need(run, "design", "Approve C1 first.")
    run.approvals.append("C2: design approved")
    try:
        run = stage_plan(run, _llm(run))
    except Exception as exc:  # noqa: BLE001
        _fail(exc)
    return render(run, "plan", "**C3:** tasks, QA plan and tests are ready. The tests were written before any code.")


def on_c3(run):
    run = _need(run, "plan", "Approve C2 first.")
    run.approvals.append("C3: tasks and QA plan approved")
    try:
        run = stage_build(run, _llm(run))
    except Exception as exc:  # noqa: BLE001
        _fail(exc)
    return render(run, "build", "**C4:** the app is live below, with its tests running inside it. Check it, then release.")


def on_c4(run):
    run = _need(run, "html", "Build the app first.")
    run.approvals.append("C4: build verified and released")
    return render(run, "package", "Released. Download the change package below.", _package(run))


def on_fast_forward(idea, po_files, arch_text, arch_files, target_file):
    llm = _llm(None)
    try:
        run = fast_forward(idea or "", _paths(po_files), arch_text or "", _paths(arch_files),
                           (_paths(target_file) or [None])[0], llm)
    except Exception as exc:  # noqa: BLE001
        _fail(exc)
    return render(run, "build", "Fast-forward complete: every checkpoint was auto-approved. The live build is below.",
                  _package(run))


def idea_to_openspec(idea: str) -> str:
    """Turn a product idea into an OpenSpec change (proposal and capability specs) using Mistral agents.

    Args:
        idea: The product idea, from a one line pitch to a few paragraphs of brief.

    Returns:
        Markdown with the product canvas, the OpenSpec proposal and spec files, and validation results.
    """
    llm = _llm(None)
    try:
        run = stage_spec(stage_canvas(stage_inputs(idea, [], "", [], None, llm), llm), llm)
    except GuardrailError as exc:
        return f"Blocked: {exc}"
    return ex.canvas_md(run.canvas) + "\n" + ex.spec_preview_md(run.spec) + "\n\n" + run.spec_report.markdown("Validation")


# ---------------- layout ----------------

with gr.Blocks(title="Product Canvas on Mistral") as demo:
    gr.Markdown(INTRO + ("\n" + DEMO_BANNER if DEMO else ""))
    state = gr.State(None)
    status = gr.Markdown()

    with gr.Tabs() as tabs:
        with gr.Tab("1 · Inputs", id="inputs"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("**Product owner inputs**: idea, briefs, Figma exports, Markdown")
                    idea = gr.Textbox(label="Idea", lines=3,
                                      placeholder="e.g. Help young savers put money aside for several goals")
                    po_files = gr.File(label="Briefs and designs (PDF, Word, Markdown, HTML, images)", file_count="multiple")
                with gr.Column():
                    gr.Markdown("**Architecture inputs**: intent, patterns, NFRs, controls, API contracts")
                    arch_text = gr.Textbox(label="Architecture notes", lines=3,
                                           placeholder="e.g. Browser only for now. No personal data leaves the device.")
                    arch_files = gr.File(label="Contracts and standards (OpenAPI JSON or YAML, Markdown)", file_count="multiple")
                with gr.Column():
                    gr.Markdown("**Target code** (optional): withheld until Explore, after the spec is approved")
                    target_file = gr.File(label="Existing prototype (HTML)", file_count="single")
            gr.Examples(
                examples=[
                    ["Help young savers put money aside for several goals and see their progress", None,
                     "Browser only prototype. No personal data leaves the device. Inputs must be labelled.", None,
                     str(EXAMPLES / "prototype_savings_pots.html")],
                    ["A weekly stock order planner for small cafes", None, "", None, None],
                    ["Brief attached", [str(EXAMPLES / "brief_merchant_onboarding.md")], "", None, None],
                ],
                inputs=[idea, po_files, arch_text, arch_files, target_file],
            )
            with gr.Row():
                start_btn = gr.Button("Start: draft canvas and architecture", variant="primary")
                ff_btn = gr.Button("Fast-forward all stages (auto-approve)")

        with gr.Tab("2 · Canvas + architecture [C0]", id="canvas"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Product canvas")
                    canvas_md = gr.Markdown()
                with gr.Column():
                    gr.Markdown("### Architecture (CALM style)")
                    arch_md = gr.Markdown()
            canvas_check = gr.Markdown()
            gr.Markdown("### Clarifying questions")
            questions_md = gr.Markdown()
            answers = gr.Textbox(label="Your answers (optional)", lines=2)
            redraft_btn = gr.Button("Redraft with my answers")
            with gr.Accordion("Edit before approving (JSON)", open=False):
                canvas_json = gr.Code(language="json", label="Canvas", interactive=True)
                arch_json = gr.Code(language="json", label="Architecture", interactive=True)
            c0_btn = gr.Button("C0 · Approve inputs and create the shared spec", variant="primary", interactive=False)

        with gr.Tab("3 · Shared spec [C1]", id="spec"):
            spec_check = gr.Markdown()
            spec_md = gr.Markdown()
            resolutions = gr.Textbox(label="Answers to conflicts", lines=2)
            respec_btn = gr.Button("Re-run spec with my answers")
            override = gr.Checkbox(label="Approve with known issues (recorded in the approvals log)")
            c1_btn = gr.Button("C1 · Approve shared spec and start delivery", variant="primary", interactive=False)

        with gr.Tab("4 · Explore + design [C2]", id="design"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### explore.md")
                    explore_md = gr.Markdown()
                with gr.Column():
                    gr.Markdown("### design.md")
                    design_md = gr.Markdown()
            c2_btn = gr.Button("C2 · Approve design and plan the work", variant="primary", interactive=False)

        with gr.Tab("5 · Tasks + tests [C3]", id="plan"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### tasks.md")
                    tasks_md = gr.Markdown()
                with gr.Column():
                    gr.Markdown("### QA plan")
                    qa_plan_md = gr.Markdown()
            plan_check = gr.Markdown()
            tests_code = gr.Code(language="javascript", label="Tests, written before the code (RED)")
            c3_btn = gr.Button("C3 · Approve plan and build", variant="primary", interactive=False)

        with gr.Tab("6 · Build + verify [C4]", id="build"):
            preview = gr.HTML()
            qa_md = gr.Markdown()
            with gr.Accordion("App code", open=False):
                html_code = gr.Code(language="html", label="app/index.html")
            c4_btn = gr.Button("C4 · Verify and release", variant="primary", interactive=False)

        with gr.Tab("7 · Package", id="package"):
            downloads = gr.File(label="OpenSpec change package (zip) and the app", file_count="multiple")
            approvals_md = gr.Markdown()

        with gr.Tab("Value + run log", id="log"):
            value_md = gr.Markdown()
            run_log = gr.Dataframe(headers=["Step", "Model", "Seconds", "Input tokens", "Output tokens", "Cost USD", "Status", "Note"],
                                   interactive=False, wrap=True)

        with gr.Tab("How it works", id="how"):
            gr.Markdown(f"""
**Agents** (instructions in `skills/*/SKILL.md`, Agent Skills format): product canvas, architecture, spec author,
explore, design, task planner, QA automation, implementation, QA review.

**Models routed by job:** writing `{SETTINGS.models.generate}` · building `{SETTINGS.models.code}` ·
independent review `{SETTINGS.models.review}` · OCR `{SETTINGS.models.ocr}` · vision `{SETTINGS.models.vision}` ·
embeddings `{SETTINGS.models.embed}` · moderation `{SETTINGS.models.moderation}`.

**Guardrails:** input limits and moderation; uploaded content treated as data; target code withheld until Explore
and never allowed to change requirements; conflicts become questions; nothing advances without approval.

**Validation:** OpenSpec rules (SHALL or MUST, WHEN/THEN scenarios, kebab-case names); traceability from every feature
and NFR to the spec, from every requirement to a task and from every scenario to a test; static build checks.

Source: [github.com/sid-jello-007/product-canvas-agent](https://github.com/sid-jello-007/product-canvas-agent)
""")

    outputs = [state, tabs, status, canvas_md, arch_md, canvas_check, questions_md, canvas_json, arch_json,
               spec_md, spec_check, explore_md, design_md, tasks_md, qa_plan_md, plan_check, tests_code,
               preview, qa_md, html_code, value_md, run_log, downloads, approvals_md,
               c0_btn, c1_btn, c2_btn, c3_btn, c4_btn]
    inputs = [idea, po_files, arch_text, arch_files, target_file]
    private = dict(api_visibility="private")

    start_btn.click(on_start, inputs, outputs, **private)
    ff_btn.click(on_fast_forward, inputs, outputs, **private)
    redraft_btn.click(on_redraft, [state, answers], outputs, **private)
    c0_btn.click(on_c0, [state, canvas_json, arch_json], outputs, **private)
    respec_btn.click(on_respec, [state, resolutions], outputs, **private)
    c1_btn.click(on_c1, [state, override], outputs, **private)
    c2_btn.click(on_c2, [state], outputs, **private)
    c3_btn.click(on_c3, [state], outputs, **private)
    c4_btn.click(on_c4, [state], outputs, **private)
    gr.api(idea_to_openspec, api_name="idea_to_openspec")


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=2).launch(mcp_server=True)
