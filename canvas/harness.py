"""A tiny browser test harness, injected into the live preview.

The QA automation agent writes tests against this API before the app exists
(RED). The implementation agent then builds until they pass (GREEN). In the
live preview the tests run inside the generated app and a results panel shows
which scenarios pass, so the human verifying the build sees evidence, not a claim.
"""
from __future__ import annotations

import html as html_lib
import json

HARNESS_JS = r"""
(function () {
  const tests = [];
  const sel = (id) => `[data-testid="${id}"]`;
  window.test = (name, fn) => tests.push({ name, fn });
  window.el = (id) => document.querySelector(sel(id));
  window.all = (id) => Array.from(document.querySelectorAll(sel(id)));
  window.exists = (id) => !!el(id);
  window.count = (id) => all(id).length;
  window.text = (id) => (el(id) ? el(id).textContent.trim() : "");
  window.tick = (ms = 50) => new Promise((r) => setTimeout(r, ms));
  window.expect = (cond, msg) => { if (!cond) throw new Error(msg || "expectation failed"); };
  const need = (id) => { const e = el(id); if (!e) throw new Error(`no element with data-testid="${id}"`); return e; };
  window.click = (id) => need(id).click();
  window.type = (id, value) => {
    const e = need(id); e.focus(); e.value = value;
    e.dispatchEvent(new Event("input", { bubbles: true }));
    e.dispatchEvent(new Event("change", { bubbles: true }));
  };
  window.select = window.type;

  async function run() {
    const results = [];
    for (const t of tests) {
      try {
        if (typeof window.__resetApp === "function") window.__resetApp();
        await tick(30);
        await Promise.race([t.fn(), new Promise((_, rej) => setTimeout(() => rej(new Error("timed out")), 4000))]);
        results.push({ name: t.name, ok: true });
      } catch (err) {
        results.push({ name: t.name, ok: false, error: String(err && err.message || err) });
      }
    }
    try { if (typeof window.__resetApp === "function") window.__resetApp(); } catch (e) {}
    render(results);
  }

  function render(results) {
    const passed = results.filter((r) => r.ok).length;
    const box = document.createElement("div");
    box.id = "__test_panel";
    box.style.cssText = "position:fixed;right:12px;bottom:12px;max-width:340px;max-height:45vh;overflow:auto;" +
      "background:#111;color:#eee;font:12px/1.4 system-ui,sans-serif;border-radius:10px;padding:10px 12px;" +
      "box-shadow:0 6px 24px rgba(0,0,0,.35);z-index:2147483647";
    const head = document.createElement("div");
    head.style.cssText = "font-weight:600;margin-bottom:6px;cursor:pointer";
    head.textContent = `Scenario tests: ${passed}/${results.length} passed (click to hide)`;
    head.onclick = () => { list.hidden = !list.hidden; };
    const list = document.createElement("div");
    for (const r of results) {
      const row = document.createElement("div");
      row.style.margin = "3px 0";
      row.textContent = (r.ok ? "✅ " : "❌ ") + r.name + (r.ok ? "" : ` (${r.error})`);
      list.appendChild(row);
    }
    box.append(head, list);
    document.body.appendChild(box);
    window.__testResults = results;
  }
  window.__runTests = run;
})();
"""


def inject_tests(app_html: str, tests_js: str) -> str:
    """Return the app with the harness and tests appended, set to run after load."""
    bundle = (
        f"<script>{HARNESS_JS}</script>\n<script>\n{tests_js}\n</script>\n"
        "<script>window.addEventListener('load', () => setTimeout(window.__runTests, 150));</script>\n"
    )
    idx = app_html.lower().rfind("</body>")
    return app_html[:idx] + bundle + app_html[idx:] if idx != -1 else app_html + bundle


def preview_iframe(app_html: str, tests_js: str | None = None, height: int = 640) -> str:
    """Sandboxed iframe for the live preview inside the Gradio page."""
    doc = inject_tests(app_html, tests_js) if tests_js else app_html
    return (
        f'<iframe title="Live preview" sandbox="allow-scripts allow-forms allow-modals" '
        f'style="width:100%;height:{height}px;border:1px solid #ddd;border-radius:10px;background:#fff" '
        f'srcdoc="{html_lib.escape(doc, quote=True)}"></iframe>'
    )


