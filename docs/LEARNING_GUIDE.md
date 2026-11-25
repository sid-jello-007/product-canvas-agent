# Learning guide: how Product Canvas works, and why

This guide follows one idea from input to a live app. Each section explains a design decision in plain terms
and gives a line you can use to explain it.

## The story of one change

A product owner types "Help young savers put money aside for several goals". The architect adds "Browser only.
No personal data leaves the device." There is also a rough HTML prototype from an earlier sprint.

### 1. Three kinds of input, kept apart (`canvas/pipeline.py: stage_inputs`)

Product inputs, architecture inputs and target code arrive separately and stay separate. The guardrails run
first: file limits, then Mistral's moderation model, and every uploaded document is wrapped as data so text
inside it cannot instruct the agents. PDFs go through Mistral OCR and design images through a Mistral vision
model, so everything becomes readable text.

The prototype is read but **held back**. Nobody writing requirements gets to see it.

*How to say it:* "Requirements come from the product and the architecture. Existing code informs delivery; it
never gets a vote on what we build."

### 2. Canvas and architecture side by side (C0)

The canvas agent drafts epics, features, acceptance criteria and test scenarios, and asks clarifying questions
when the brief is silent. The architecture agent drafts a small model of the system in the style of FINOS CALM
(nodes such as "web app" and "browser storage", and the relationships between them), plus decisions and
measurable NFRs.

You answer the questions, edit anything, and approve. That approval is C0.

*How to say it:* "Two owners, two artefacts, one gate. Product and architecture agree before anyone specifies."

### 3. One shared spec: normalise, clarify, validate (C1)

The spec agent turns both into an OpenSpec change: a proposal (why, what changes, impact) and one spec file per
capability. Each requirement uses SHALL or MUST and has scenarios written as WHEN/THEN. These are the same plain
Markdown files a team would keep in its repo.

Two things make it trustworthy:
- **The conflict guardrail.** If a feature contradicts an NFR, the agent does not choose. It writes the safest
  version and raises a question. Approval is blocked until you answer, or you explicitly accept the risk, which
  is recorded.
- **Validation without a model.** A script checks every rule (SHALL or MUST, WHEN/THEN, kebab-case names) and
  traceability: every feature and every NFR must reach the spec. Embeddings flag requirements that say the same thing.

*How to say it:* "The spec is the contract. Agents propose it, scripts check it, a human signs it."

### 4. Explore, then design (C2)

Only now does an agent see the prototype. It records what already exists, what has to change, and any risks.
The design agent then writes design.md: approach, decisions, the screens with the test id of every element a
test will touch, and the test strategy.

*How to say it:* "First code access comes after the spec is approved, so the code adapts to the requirements,
not the other way round."

### 5. Tasks, then tests before code (C3)

The planning agent writes tasks.md, a numbered checklist where every task names the requirements it delivers,
and a QA plan with one test per scenario. Then Mistral's code model writes executable tests **before any app
exists**. This is the RED step: the tests describe done.

*How to say it:* "If you write the tests after the code, they test what was built. Written first, they test what
was asked for."

### 6. Build, review, triage, fix (C4)

The code model builds the app to make the tests pass (GREEN). Then three checks run:
- **Static checks** in Python: a complete page, no external calls, a reset hook, and every test id the tests
  use actually exists in the code.
- **An independent reviewer**, a different Mistral model, traces every scenario to evidence in the code.
- **Triage**: each failure is assigned to its owner. App failures go back to the builder for one fix round;
  test or spec problems are routed to a person.

Finally the app runs live in the page with the tests running inside it, and a panel shows which scenarios pass.
You look at the evidence and approve the release.

*How to say it:* "The builder never marks its own homework. A separate reviewer and real tests do, and a human
sees the evidence before release."

### 7. The package

The output is laid out the way a repo holds it: `openspec/changes/<id>/` with proposal, specs, design, tasks and
explore; the CALM style JSON; a Jira import; the app, its tests and the QA report. An OpenSpec aware coding agent
can pick up the change folder directly.

## Ideas worth being able to explain

- **Structured outputs.** Every agent must return JSON in a fixed shape (`canvas/schemas.py`). Mistral enforces
  it as the model writes; Pydantic checks it again. Agents become components with contracts.
- **Model routing.** Large writes the product artefacts, Codestral writes code, Medium reviews. Matching the model
  to the job controls cost and keeps the reviewer independent of the builder.
- **Skills as files.** Each agent's instructions are a `SKILL.md`. Changing behaviour is editing a document, and
  the change is visible in review.
- **Evals.** `evals/run_evals.py` runs the full flow on fixed ideas and writes a scorecard, so you can prove a
  change to a skill or model made things better, not just different.
- **Demo mode.** A fake model returns a full sample run, so tests run free in CI and the public app still works
  without a key. The sample's first build has a real bug, so the review and fix loop is visible.

## Exercises

1. **Tighten a rule.** In `canvas/evals.py`, require two scenarios per requirement. Run `pytest`, see what breaks,
   then update `skills/spec-author/SKILL.md` to match.
2. **Force a conflict.** Ask for "sync savings across devices" with the architecture note "no data leaves the
   device". Watch the spec agent raise it as a question.
3. **Swap the builder.** Set `MODEL_CODE=mistral-large-latest`, run the evals, and compare first build pass rates
   and cost with Codestral.
4. **Break the build on purpose.** Edit a test to use a test id that does not exist. Which check catches it?
5. **Read the run log.** Which stage is slowest and which is most expensive? What would you change first for a
   customer with 200 product managers?
