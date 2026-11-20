"""Product Canvas web app (Gradio), deployed as a Hugging Face Space.

Also exposes one clean tool over MCP, so the same workflow can be called
from Mistral Le Chat (custom connector), Claude or any MCP client.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import gradio as gr

from canvas import exporters
from canvas.guardrails import GuardrailError
from canvas.llm import make_llm, to_json
from canvas.pipeline import build_backlog, build_canvas
from canvas.config import SETTINGS
from canvas.schemas import ProductCanvas
from canvas.telemetry import Telemetry

EXAMPLES_DIR = Path(__file__).parent / "examples"
_, DEMO = make_llm()

INTRO = """# Product Canvas
**Idea in, Jira ready backlog out.** Give it a one line idea, a brief (PDF, Word, Markdown), an HTML prototype
or a design screenshot. Mistral agents draft a **product canvas** for you to review, then a **spec** and
**tickets**, check their own work against INVEST and coverage rules, fix weak stories, and export to Jira.
"""
DEMO_BANNER = "> **Demo mode.** No `MISTRAL_API_KEY` is configured, so you will see a sample output and no model is called."


def _friendly(exc: Exception) -> gr.Error:
    if isinstance(exc, GuardrailError):
        return gr.Error(str(exc))
    return gr.Error(f"Something went wrong: {exc}")


def run_stage_one(idea, files):
    telemetry = Telemetry()
    llm, _ = make_llm(telemetry)
    paths = [f if isinstance(f, str) else f.name for f in (files or [])]
    try:
        result = build_canvas(idea or "", paths, llm)
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc) from exc
    status = f"**Read:** {result.context.summary()}"
    if result.warnings:
        status += "\n\n" + "\n".join(f"> ⚠️ {w}" for w in result.warnings)
    status += "\n\n**Next:** review the canvas, edit the JSON if needed, then approve it to generate the spec and tickets."
    return (
        status,
        exporters.canvas_markdown(result.canvas),
        to_json(result.canvas),
        result.context.as_prompt(),
        telemetry,
        gr.update(interactive=True),
    )


def run_stage_two(canvas_json, context_prompt, telemetry):
    if not canvas_json:
        raise gr.Error("Build a canvas first.")
    try:
        canvas = ProductCanvas.model_validate_json(canvas_json)
    except Exception as exc:  # noqa: BLE001
        raise gr.Error(f"The edited canvas is not valid JSON for the schema: {exc}") from exc
    telemetry = telemetry or Telemetry()
    llm, _ = make_llm(telemetry)
    try:
        res = build_backlog(canvas, context_prompt or "", llm)
    except Exception as exc:  # noqa: BLE001
        raise _friendly(exc) from exc

    q, k = res.quality, res.kpis
    issues = q.combined_issues()
    open_issues = "\n".join(f"- **{key}**: {'; '.join(v)}" for key, v in issues.items() if v) or "- None"
    dupes = "\n".join(f"- {a} and {b} (similarity {s})" for a, b, s in q.duplicates) or "- None found"
    quality_md = f"""### Quality score: {q.overall}/100 (first draft scored {res.first_pass_score})
| Check | Result |
|---|---|
| Stories passing all rules | {q.rule_pass_rate:.0%} of {q.stories_total} |
| INVEST score from judge model | {q.avg_judge_score:.1f} / 5 |
| Must and Should requirements without a story | {', '.join(q.uncovered_requirements) or 'none'} |
| Stories rewritten by the refine agent | {', '.join(q.refined_keys) or 'none'} |

**Judge's comment:** {q.judge_comment}

**Open issues after refinement**
{open_issues}

**Possible duplicate stories (Mistral embeddings)**
{dupes}
""" + ("\n" + "\n".join(f"> {n}" for n in res.notes) if res.notes else "")

    totals = telemetry.totals()
    value_md = f"""### Business value of this run
| Measure | Value |
|---|---|
| Stories drafted | {k['stories']} |
| Manual effort replaced (estimate) | {k['manual_hours_estimate']} hours, about £{k['manual_cost_gbp']:,} |
| Time taken | {totals['seconds']} seconds across {totals['calls']} model calls |
| Model cost (estimate) | ${totals['cost_usd']:.4f} ({totals['input_tokens']:,} input, {totals['output_tokens']:,} output tokens) |

*Assumptions: {k['assumptions']}. Prices are indicative; see config.py.*
"""

    out = Path(tempfile.mkdtemp())
    (out / "jira_import.csv").write_text(exporters.jira_csv(res.plan), encoding="utf-8")
    (out / "product_spec.md").write_text(
        "# Product canvas\n" + exporters.canvas_markdown(canvas) + "\n# Spec\n" + exporters.spec_markdown(res.spec)
        + "\n# Backlog\n" + exporters.tickets_markdown(res.plan), encoding="utf-8")
    (out / "backlog.json").write_text(json.dumps({
        "canvas": canvas.model_dump(), "spec": res.spec.model_dump(), "tickets": res.plan.model_dump(),
    }, indent=2), encoding="utf-8")

    return (
        exporters.spec_markdown(res.spec),
        exporters.ticket_rows(res.plan),
        exporters.tickets_markdown(res.plan),
        quality_md,
        value_md,
        telemetry.rows(),
        [str(out / "jira_import.csv"), str(out / "product_spec.md"), str(out / "backlog.json")],
        telemetry,
    )


def idea_to_backlog(idea: str) -> str:
    """Turn a product idea into a product canvas, spec and Jira style backlog using Mistral agents.

    Args:
        idea: The product idea, from a one line pitch to a few paragraphs of brief.

    Returns:
        Markdown containing the canvas, spec, tickets and a quality score.
    """
    llm, _ = make_llm(Telemetry())
    try:
        c = build_canvas(idea, [], llm)
        r = build_backlog(c.canvas, c.context.as_prompt(), llm)
    except GuardrailError as exc:
        return f"Blocked: {exc}"
    return (
        exporters.canvas_markdown(c.canvas) + "\n" + exporters.spec_markdown(r.spec)
        + "\n" + exporters.tickets_markdown(r.plan) + f"\n\nQuality score: {r.quality.overall}/100"
    )


with gr.Blocks(title="Product Canvas on Mistral") as demo:
    gr.Markdown(INTRO + ("\n" + DEMO_BANNER if DEMO else ""))
    context_state = gr.State("")
    telemetry_state = gr.State(None)

    with gr.Row():
        with gr.Column(scale=3):
            idea = gr.Textbox(label="Idea", lines=3, placeholder="e.g. An app that lets flatmates split bills and settle up automatically")
        with gr.Column(scale=2):
            files = gr.File(label="Optional: briefs, prototypes or designs", file_count="multiple",
                            file_types=[".pdf", ".docx", ".md", ".txt", ".html", ".png", ".jpg", ".jpeg", ".webp"])
    gr.Examples(
        examples=[
            ["A tool that helps small cafes predict how much stock to order each week", None],
            ["Brief attached", [str(EXAMPLES_DIR / "brief_merchant_onboarding.md")]],
            ["Prototype attached", [str(EXAMPLES_DIR / "prototype_savings_pots.html")]],
        ],
        inputs=[idea, files],
    )
    canvas_btn = gr.Button("1. Build product canvas", variant="primary")
    status = gr.Markdown()

    with gr.Tabs():
        with gr.Tab("Canvas"):
            canvas_md = gr.Markdown()
            with gr.Accordion("Edit the canvas before approving (JSON)", open=False):
                canvas_json = gr.Code(language="json", interactive=True, label="Canvas JSON")
            backlog_btn = gr.Button("2. Approve canvas, generate spec and tickets", variant="primary", interactive=False)
        with gr.Tab("Spec"):
            spec_md = gr.Markdown()
        with gr.Tab("Tickets"):
            ticket_table = gr.Dataframe(headers=["Epic", "Key", "Title", "Points", "Priority", "Requirements", "Depends on"],
                                        interactive=False, wrap=True)
            tickets_md = gr.Markdown()
        with gr.Tab("Quality"):
            quality_md = gr.Markdown("Run stage 2 to see the evaluation.")
        with gr.Tab("Value and run log"):
            value_md = gr.Markdown()
            run_log = gr.Dataframe(headers=["Step", "Model", "Seconds", "Input tokens", "Output tokens", "Cost USD", "Status", "Note"],
                                   interactive=False, wrap=True)
        with gr.Tab("Export"):
            downloads = gr.File(label="Jira CSV, markdown spec, JSON", file_count="multiple")
        with gr.Tab("How it works"):
            gr.Markdown(f"""
**Models used (routed by job):** generation `{SETTINGS.models.generate}`, judge `{SETTINGS.models.judge}`,
vision `{SETTINGS.models.vision}`, OCR `{SETTINGS.models.ocr}`, embeddings `{SETTINGS.models.embed}`,
moderation `{SETTINGS.models.moderation}`.

1. **Guardrails:** input limits, Mistral moderation, untrusted content wrapped as data.
2. **Ingest:** PDFs via Mistral OCR, designs via a Mistral vision model, HTML and Word parsed directly.
3. **Canvas agent** drafts the product canvas. **You review it** (human in the loop).
4. **Spec agent** writes requirements; **ticket agent** writes epics and stories as strict JSON.
5. **Evaluation:** rule checks plus an INVEST judge model; weak stories go to a **refine agent** and are re-scored.
6. **Embeddings** flag near duplicate stories. **Run log** records latency, tokens and cost per step.
7. **Export** to Jira CSV, markdown or JSON. The workflow is also exposed as an **MCP tool**.

Source code and docs: [github.com/sid-jello-007/product-canvas-agent](https://github.com/sid-jello-007/product-canvas-agent)
""")

    canvas_btn.click(
        run_stage_one, [idea, files],
        [status, canvas_md, canvas_json, context_state, telemetry_state, backlog_btn],
        api_visibility="private",
    )
    backlog_btn.click(
        run_stage_two, [canvas_json, context_state, telemetry_state],
        [spec_md, ticket_table, tickets_md, quality_md, value_md, run_log, downloads, telemetry_state],
        api_visibility="private",
    )
    gr.api(idea_to_backlog, api_name="idea_to_backlog")


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=2).launch(mcp_server=True)
