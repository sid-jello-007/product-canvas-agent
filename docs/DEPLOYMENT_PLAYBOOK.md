# Deployment playbook: taking Product Canvas from demo to production at a customer

A demo proves the model can do the task. A deployment proves the customer gets value from it, safely,
inside the way they already work. This is how I would run that for a product organisation adopting
Product Canvas.

## 1. Discovery workshop (week 0)

Goal: find where the time actually goes between "we have an idea" and "something working that users can try".

Questions to ask:
- How long does it take today to go from an idea to a groomed, estimated backlog? Who is involved?
- How often are stories sent back in refinement because they are unclear or untestable?
- Where do briefs and designs live (Confluence, Figma, SharePoint)? Where do tickets live?
- What can and cannot leave the company's environment? Any regulated data in briefs?
- Who signs off a spec today? That person becomes the human in the loop.

Output: a baseline for the pilot KPIs, the target squads, and the data and security constraints.

## 2. Solution design

| Decision | Default | When to change it |
|---|---|---|
| Models | Large to write, Small to judge | Small everywhere if cost matters more than polish; self deployed open weights if data must stay on site |
| Inputs | Uploads | Connect Confluence and Figma once the pilot proves value |
| Output | OpenSpec change folder and Jira CSV | Open a pull request with the change folder; Jira API with a "draft" status |
| Human checkpoints | C0 to C4 | Keep C1 and C4 mandatory; allow fast-forward through C2 and C3 once trust is earned |
| Target | Single file prototype | One delivery per affected repo (frontend, API, database) from the same shared spec |
| Guardrails | Moderation, PII warning, untrusted content rule | Add redaction before the model call if briefs contain customer data |

## 3. Pilot (4 to 6 weeks, 2 squads)

Run Product Canvas alongside the normal process on real work.

| KPI | How it is measured | Pilot target |
|---|---|---|
| Idea to approved spec | Calendar days, before vs during pilot | 50% faster |
| Spec approved without rework | Share of changes approved at C1 with no validation errors or open conflicts | 70% |
| First build pass rate | Scenarios passing before any fix round, from the scorecard | 80% |
| Requirements traced end to end | Feature to requirement to task to test, from validation | 100% |
| Cost per change | Run log | Under $1 |
| PM hours saved | PM time sheets or self report vs baseline | 4+ hours per feature |
| Adoption | Weekly active PMs in pilot squads | 80% |

Weekly: review the run log and quality scores, collect the stories PMs rewrote, and turn the patterns
into prompt or rule changes. Re-run the eval scorecard after every change so quality never silently drops.

## 4. Business case for scale

Value per change = product, architecture and prototyping hours saved x loaded hourly rate + earlier user feedback.
Cost per change = model cost (cents) + platform and support cost.
The value tab in the app shows this per run with the assumptions visible, so the sponsor can challenge them.

## 5. Scale

- Connect the customer's sources (Confluence, Figma) and Jira through connectors or MCP.
- Add SSO, audit logging and usage dashboards from the telemetry events.
- Package each team's conventions as skills (their spec style, their definition of done) instead of code changes.
- Train champions in each tribe; publish a short "good canvas" guide from the pilot's best examples.

## Risks and controls

| Risk | Control |
|---|---|
| Plausible but wrong requirements | Human approval at C0 and C1; clarifying questions and conflicts surfaced explicitly |
| Existing code quietly redefining scope | Target code withheld until Explore and given no authority over requirements |
| Agents marking their own work | Tests written before code; independent reviewer on a different model; evidence shown before release |
| Prompt injection through uploaded docs | Documents wrapped as data; agents told to ignore instructions inside them |
| Sensitive data in briefs | Moderation flags personal data; redaction or on premises deployment for regulated teams |
| Quality drift after changes | Golden set scorecard run in CI before every release |
| Cost surprises | Context budget, model routing, per run cost in the log |
