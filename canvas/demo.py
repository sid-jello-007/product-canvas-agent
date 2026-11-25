"""Canned outputs for demo mode and tests.

Demo mode lets anyone click through every stage without an API key. The first
build deliberately shows progress without a percentage, so the tests fail,
QA triages it to the app owner, and the fix round turns it green: the whole
evaluator and optimiser loop is visible.
"""
from .schemas import Architecture, DesignDoc, Exploration, ProductCanvas, QAReview, SpecPackage, TaskPlan

CANVAS = {
    "product_name": "Savings Pots",
    "change_id": "add-savings-pots",
    "problem": "People who save for several goals at once lose track of how close they are, so they stop saving.",
    "target_users": ["Young professionals saving for 2 or 3 goals", "Students building a first emergency fund"],
    "value_proposition": "Name a goal, put money aside and always see how close you are.",
    "epics": [{
        "title": "Save towards goals",
        "outcome": "Users can set goals and see progress at a glance",
        "features": [
            {"title": "Create a pot", "description": "Create a named pot with a goal amount.",
             "acceptance_criteria": ["A pot needs a name and a goal above zero", "New pots appear in the list immediately"],
             "test_scenarios": ["when I create 'Holiday' with goal 1200, then it appears in my list",
                                "when I leave the name empty, then I see an error and no pot is created"]},
            {"title": "Add money to a pot", "description": "Add an amount to an existing pot.",
             "acceptance_criteria": ["The saved total increases by the amount added", "Amounts must be above zero"],
             "test_scenarios": ["when I add 250 to a pot, then its saved total shows £250"]},
            {"title": "See progress", "description": "Each pot shows how far it is towards its goal.",
             "acceptance_criteria": ["Progress is shown as a percentage of the goal", "A bar shows progress visually"],
             "test_scenarios": ["when a 400 goal has 100 saved, then progress shows 25%"]},
        ],
    }],
    "success_metrics": [{"name": "Users with 2+ pots after 30 days", "target": "40%"},
                        {"name": "Pots that reach their goal within 6 months", "target": "25%"}],
    "out_of_scope": ["Moving real money", "Bank account connections", "Interest"],
    "assumptions": ["Amounts are in GBP", "One user per device for the first release"],
    "clarifying_questions": [],
}

ARCH = {
    "intent": "A single page web prototype that runs entirely in the browser so the idea can be tested with users quickly.",
    "patterns": ["Single page app", "Local first storage", "Progressive enhancement"],
    "nodes": [
        {"unique_id": "saver", "node_type": "actor", "name": "Saver", "description": "Person saving towards goals"},
        {"unique_id": "pots-web", "node_type": "webclient", "name": "Savings Pots web app", "description": "Single HTML file app"},
        {"unique_id": "browser-store", "node_type": "database", "name": "Browser localStorage", "description": "Pots stored on the device"},
    ],
    "relationships": [
        {"unique_id": "saver-uses-app", "source": "saver", "destination": "pots-web", "protocol": "HTTPS", "description": "Saver uses the app in a browser"},
        {"unique_id": "app-stores-pots", "source": "pots-web", "destination": "browser-store", "protocol": "browser storage", "description": "App saves and loads pots"},
    ],
    "decisions": [
        {"title": "No backend for the prototype", "decision": "Keep all data in localStorage", "rationale": "Fastest route to user testing; no personal data leaves the device"},
        {"title": "Vanilla JavaScript", "decision": "No framework or build step", "rationale": "One file that anyone can open and review"},
    ],
    "nfrs": [
        {"id": "NFR-1", "category": "accessibility", "statement": "Every input SHALL have a visible label."},
        {"id": "NFR-2", "category": "privacy", "statement": "The app SHALL NOT send any data off the device."},
        {"id": "NFR-3", "category": "usability", "statement": "The app SHALL be usable at 375px screen width."},
    ],
    "controls": ["No third party scripts", "No personal data beyond pot names and amounts"],
    "interfaces": [{"name": "Pots screen", "kind": "ui", "description": "Create pots, add money, see progress"},
                   {"name": "Pot store", "kind": "storage", "description": "JSON list of pots in localStorage"}],
}


def _sc(name, when, then, given=""):
    return {"name": name, "given": given, "when": when, "then": then}


SPEC = {
    "proposal": {
        "why": "Savers with several goals lose track of progress and stop saving. Visible goals and progress keep them going.",
        "what_changes": ["Create named savings pots with goals", "Add money to a pot", "Show progress towards each goal"],
        "impact": "New web prototype; no existing systems change. Data stays in the browser.",
    },
    "capabilities": [
        {"name": "pot-management", "purpose": "Create pots and add money to them.", "requirements": [
            {"name": "Create pot", "statement": "The system SHALL let a user create a pot with a name and a goal above zero.",
             "kind": "functional", "traces_to": ["Create a pot"], "scenarios": [
                 _sc("Create a pot with a goal", "the user creates 'Holiday' with goal 1200", "the pot appears in the pot list"),
                 _sc("Reject a pot without a name", "the user submits a goal without a name", "an error is shown and no pot is created")]},
            {"name": "Add money", "statement": "The system SHALL increase a pot's saved total by the amount added.",
             "kind": "functional", "traces_to": ["Add money to a pot"], "scenarios": [
                 _sc("Add money to a pot", "the user adds 250", "the pot shows £250 saved", given="a pot with goal 1000")]},
        ]},
        {"name": "progress-tracking", "purpose": "Show how close each pot is to its goal.", "requirements": [
            {"name": "Show progress", "statement": "The system SHALL show each pot's progress as a percentage of its goal.",
             "kind": "functional", "traces_to": ["See progress"], "scenarios": [
                 _sc("Progress shows percentage of goal", "100 is saved towards a 400 goal", "progress shows 25%")]},
        ]},
        {"name": "privacy-and-accessibility", "purpose": "Non-functional guarantees from the architecture.", "requirements": [
            {"name": "Labelled inputs", "statement": "Every input SHALL have a visible label.", "kind": "non-functional",
             "traces_to": ["NFR-1"], "scenarios": [_sc("Inputs are labelled", "the pots screen loads", "the name and goal inputs have labels")]},
            {"name": "Data stays on device", "statement": "The app SHALL NOT send data off the device.", "kind": "non-functional",
             "traces_to": ["NFR-2"], "scenarios": [_sc("Data stays on the device", "the app is used", "no external scripts or network calls exist")]},
            {"name": "Mobile width", "statement": "The layout SHALL fit a 375px wide screen without horizontal scrolling.",
             "kind": "non-functional", "traces_to": ["NFR-3"], "scenarios": [_sc("Fits a phone screen", "the screen is 375px wide", "no horizontal scrolling is needed")]},
        ]},
    ],
    "conflicts": [],
}

EXPLORE = {
    "target_summary": "Static HTML prototype of a pots screen with hard coded pots and no behaviour.",
    "baseline_findings": ["Page title and headings for 'Your pots' exist", "Pot name and goal inputs exist without test ids", "No JavaScript and no storage"],
    "implementation_delta": ["Add create pot behaviour with validation", "Add money input per pot", "Compute and show percentage progress",
                             "Persist pots in localStorage", "Add data-testid values for every tested element"],
    "risks": ["Prototype shows round ups and locking, which are out of scope for this change"],
}

DESIGN = {
    "context": "Evolve the static prototype into a working single file app.",
    "goals": ["Meet every requirement in the approved spec", "Stay a single self contained file"],
    "non_goals": ["Round ups", "Locking pots", "Any backend"],
    "decisions": [{"title": "Render from state", "decision": "Re-render the pot list from an array after every change", "rationale": "Simple and testable"}],
    "ui_structure": ["New pot form: name input (data-testid=pot-name), goal input (data-testid=pot-goal), create button (data-testid=create-pot), error text (data-testid=form-error)",
                     "Pot list (data-testid=pot-list) with one card per pot (data-testid=pot-card)",
                     "In each card: progress text (data-testid=pot-progress), amount input (data-testid=add-amount), add button (data-testid=add-money)"],
    "state_and_data": "An array of {name, goal, saved} saved as JSON under one localStorage key, loaded on start.",
    "test_strategy": "Each scenario is driven through the UI by test id; window.__resetApp clears state before each test.",
    "risks_and_tradeoffs": ["localStorage is blocked in some sandboxes, so the app falls back to memory"],
}

PLAN = {
    "groups": [
        {"number": 1, "title": "Pots", "tasks": [
            {"id": "1.1", "description": "Build the new pot form with labels and validation", "requirements": ["Create pot", "Labelled inputs"]},
            {"id": "1.2", "description": "Render the pot list from state and persist to localStorage", "requirements": ["Create pot", "Data stays on device"]},
            {"id": "1.3", "description": "Add money to a pot", "requirements": ["Add money"]}]},
        {"number": 2, "title": "Progress and layout", "tasks": [
            {"id": "2.1", "description": "Show percentage progress and a progress bar", "requirements": ["Show progress"]},
            {"id": "2.2", "description": "Responsive layout for 375px screens", "requirements": ["Mobile width"]}]},
    ],
    "qa_plan": [
        {"scenario": "Create a pot with a goal", "test_name": "Create a pot with a goal", "steps": ["type Holiday in pot-name", "type 1200 in pot-goal", "click create-pot", "check pot-list contains Holiday"]},
        {"scenario": "Reject a pot without a name", "test_name": "Reject a pot without a name", "steps": ["type 500 in pot-goal", "click create-pot", "check no pot-card and form-error shown"]},
        {"scenario": "Add money to a pot", "test_name": "Add money to a pot", "steps": ["create a pot", "type 250 in add-amount", "click add-money", "check pot-card shows £250"]},
        {"scenario": "Progress shows percentage of goal", "test_name": "Progress shows percentage of goal", "steps": ["create a 400 pot", "add 100", "check pot-progress shows 25%"]},
        {"scenario": "Inputs are labelled", "test_name": "Inputs are labelled", "steps": ["check pot-name and pot-goal have labels"]},
        {"scenario": "Data stays on the device", "test_name": "Data stays on the device", "steps": ["check there are no external scripts"]},
        {"scenario": "Fits a phone screen", "test_name": "Fits a phone screen", "steps": ["check the page is not wider than the viewport"]},
    ],
}

TESTS = """test("Create a pot with a goal", async () => {
  type("pot-name", "Holiday"); type("pot-goal", "1200"); click("create-pot"); await tick();
  expect(count("pot-card") === 1, "one pot card is shown");
  expect(text("pot-list").includes("Holiday"), "pot name appears in the list");
});

test("Reject a pot without a name", async () => {
  type("pot-goal", "500"); click("create-pot"); await tick();
  expect(count("pot-card") === 0, "no pot is created");
  expect(text("form-error").length > 0, "an error message is shown");
});

test("Add money to a pot", async () => {
  type("pot-name", "Laptop"); type("pot-goal", "1000"); click("create-pot"); await tick();
  type("add-amount", "250"); click("add-money"); await tick();
  expect(text("pot-card").includes("£250"), "saved total shows £250");
});

test("Progress shows percentage of goal", async () => {
  type("pot-name", "Car"); type("pot-goal", "400"); click("create-pot"); await tick();
  type("add-amount", "100"); click("add-money"); await tick();
  expect(text("pot-progress").includes("25%"), "progress shows 25%");
});

test("Inputs are labelled", async () => {
  expect(el("pot-name").labels.length > 0 && el("pot-goal").labels.length > 0, "name and goal inputs have labels");
});

test("Data stays on the device", async () => {
  expect(!document.querySelector('script[src^="http"], link[href^="http"]'), "no external scripts or stylesheets");
});

test("Fits a phone screen", async () => {
  expect(document.documentElement.scrollWidth <= window.innerWidth + 1, "no horizontal scrolling");
});
"""

_APP = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Savings Pots</title>
<!-- Savings Pots: generated from openspec change add-savings-pots -->
<style>
  :root { --ink:#1d1d1f; --muted:#5b5b66; --line:#e3e3ea; --accent:#ff7000; --bg:#fafafa; }
  * { box-sizing: border-box; }
  body { margin:0; font:16px/1.5 system-ui, -apple-system, Segoe UI, sans-serif; color:var(--ink); background:var(--bg); }
  main { max-width:560px; margin:0 auto; padding:20px 16px 120px; }
  h1 { font-size:1.6rem; margin:0 0 4px; }
  .sub { color:var(--muted); margin:0 0 20px; }
  form.new { display:grid; gap:8px; background:#fff; border:1px solid var(--line); border-radius:12px; padding:16px; }
  label { font-weight:600; font-size:.9rem; }
  input { width:100%; padding:10px 12px; border:1px solid #c9c9d3; border-radius:8px; font:inherit; }
  button { padding:10px 14px; border:0; border-radius:8px; background:var(--accent); color:#fff; font:inherit; font-weight:600; cursor:pointer; }
  .error { color:#b00020; min-height:1.2em; margin:0; font-size:.9rem; }
  .list { display:grid; gap:12px; margin-top:20px; }
  .card { background:#fff; border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
  .card h2 { font-size:1.1rem; margin:0 0 6px; }
  .bar { height:8px; background:#eee; border-radius:99px; overflow:hidden; margin:6px 0 10px; }
  .bar span { display:block; height:100%; background:var(--accent); }
  .add { display:flex; gap:8px; }
  .add input { flex:1; min-width:0; }
  .empty { color:var(--muted); }
</style>
</head>
<body>
<main>
  <h1>Savings pots</h1>
  <p class="sub">Set a goal, put money aside, watch it grow.</p>
  <form class="new" id="new-pot">
    <label for="pot-name-input">Pot name</label>
    <input id="pot-name-input" data-testid="pot-name" placeholder="e.g. Holiday" autocomplete="off">
    <label for="pot-goal-input">Goal (£)</label>
    <input id="pot-goal-input" data-testid="pot-goal" type="number" min="1" inputmode="decimal" placeholder="e.g. 1200">
    <button type="submit" data-testid="create-pot">Create pot</button>
    <p class="error" role="alert" data-testid="form-error"></p>
  </form>
  <section class="list" data-testid="pot-list" aria-live="polite"></section>
</main>
<script>
  const KEY = "savings-pots-v1";
  const memory = { pots: [] };
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch (e) { return memory.pots; } };
  const save = () => { memory.pots = pots; try { localStorage.setItem(KEY, JSON.stringify(pots)); } catch (e) {} };
  let pots = load();

  const nameInput = document.getElementById("pot-name-input");
  const goalInput = document.getElementById("pot-goal-input");
  const error = document.querySelector('[data-testid="form-error"]');
  const list = document.querySelector('[data-testid="pot-list"]');
  const money = (n) => "£" + n.toLocaleString("en-GB");

  function progressText(p) {
    return __PROGRESS__;
  }

  function render() {
    list.innerHTML = "";
    if (!pots.length) { list.innerHTML = '<p class="empty">No pots yet. Create your first one above.</p>'; return; }
    pots.forEach((p, i) => {
      const card = document.createElement("article");
      card.className = "card"; card.dataset.testid = "pot-card";
      const title = document.createElement("h2"); title.textContent = p.name;
      const prog = document.createElement("p"); prog.dataset.testid = "pot-progress"; prog.textContent = progressText(p);
      const bar = document.createElement("div"); bar.className = "bar";
      const fill = document.createElement("span"); fill.style.width = Math.min(100, (p.saved / p.goal) * 100) + "%"; bar.appendChild(fill);
      const add = document.createElement("form"); add.className = "add";
      const id = "amount-" + i;
      add.innerHTML = '<label for="' + id + '" style="position:absolute;left:-9999px">Amount to add</label>' +
        '<input id="' + id + '" data-testid="add-amount" type="number" min="1" placeholder="Amount (£)">' +
        '<button type="submit" data-testid="add-money">Add money</button>';
      add.addEventListener("submit", (ev) => {
        ev.preventDefault();
        const amount = Number(add.querySelector("input").value);
        if (!(amount > 0)) return;
        p.saved += amount; save(); render();
      });
      card.append(title, prog, bar, add);
      list.appendChild(card);
    });
  }

  document.getElementById("new-pot").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const name = nameInput.value.trim();
    const goal = Number(goalInput.value);
    if (!name) { error.textContent = "Give your pot a name."; return; }
    if (!(goal > 0)) { error.textContent = "Set a goal above £0."; return; }
    error.textContent = "";
    pots.push({ name, goal, saved: 0 }); save();
    nameInput.value = ""; goalInput.value = "";
    render();
  });

  window.__resetApp = () => {
    pots = []; save();
    nameInput.value = ""; goalInput.value = ""; error.textContent = "";
    render();
  };

  render();
</script>
</body>
</html>
"""

APP_V1 = _APP.replace("__PROGRESS__", 'money(p.saved) + " of " + money(p.goal)')
APP_V2 = _APP.replace("__PROGRESS__", 'money(p.saved) + " of " + money(p.goal) + " (" + Math.round((p.saved / p.goal) * 100) + "%)"')

_SCENARIOS = [s["name"] for c in SPEC["capabilities"] for r in c["requirements"] for s in r["scenarios"]]


def _review(fixed: bool) -> QAReview:
    results = []
    for name in _SCENARIOS:
        if name == "Progress shows percentage of goal" and not fixed:
            results.append({"scenario": name, "status": "fail", "owner": "app",
                            "evidence": "progressText() shows '£100 of £400' but never a percentage"})
        else:
            results.append({"scenario": name, "status": "pass", "owner": "none", "evidence": "Implemented in render() and the form handlers"})
    summary = "All scenarios are implemented and tested." if fixed else "One scenario fails: progress has no percentage."
    return QAReview.model_validate({"results": results, "summary": summary})


def respond(schema, user_prompt: str):
    table = {ProductCanvas: CANVAS, Architecture: ARCH, SpecPackage: SPEC, Exploration: EXPLORE,
             DesignDoc: DESIGN, TaskPlan: PLAN}
    if schema in table:
        return schema.model_validate(table[schema])
    if schema is QAReview:
        return _review(fixed="Math.round(" in user_prompt)
    raise ValueError(f"No demo response for {schema.__name__}")


def respond_text(step: str, user_prompt: str) -> str:
    if "QA automation" in step:
        return f"```javascript\n{TESTS}```"
    if "fix" in step:
        return f"```html\n{APP_V2}```"
    return f"```html\n{APP_V1}```"
