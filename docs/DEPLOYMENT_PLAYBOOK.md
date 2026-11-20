# Deployment playbook: taking Product Canvas from demo to production at a customer

A demo proves the model can do the task. A deployment proves the customer gets value from it, safely,
inside the way they already work. This is how I would run that for a product organisation adopting
Product Canvas.

## 1. Discovery workshop (week 0)

Goal: find where the time actually goes between "we have an idea" and "the team can start building".

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
| Output | Jira CSV | Jira API with a "draft" status once teams trust the output |
| Human checkpoint | Canvas approval | Add a second checkpoint on the spec for regulated products |
| Guardrails | Moderation, PII warning, untrusted content rule | Add redaction before the model call if briefs contain customer data |

## 3. Pilot (4 to 6 weeks, 2 squads)

Run Product Canvas alongside the normal process on real work.

| KPI | How it is measured | Pilot target |
|---|---|---|
| Idea to ready backlog | Calendar days, before vs during pilot | 50% faster |
| Stories accepted without rewrite | Share of generated stories that survive refinement unchanged or with light edits | 70% |
| Quality score | Built in evaluation, tracked per run | 85+ |
| Cost per backlog | Run log | Under $0.50 |
| PM hours saved | PM time sheets or self report vs baseline | 4+ hours per feature |
| Adoption | Weekly active PMs in pilot squads | 80% |

Weekly: review the run log and quality scores, collect the stories PMs rewrote, and turn the patterns
into prompt or rule changes. Re-run the eval scorecard after every change so quality never silently drops.

## 4. Business case for scale

Value per feature = PM hours saved x loaded hourly rate + earlier delivery.
Cost per feature = model cost (pennies) + platform and support cost.
The value tab in the app shows this per run with the assumptions visible, so the sponsor can challenge them.

## 5. Scale

- Connect the customer's sources (Confluence, Figma) and Jira through connectors or MCP.
- Add SSO, audit logging and usage dashboards from the telemetry events.
- Package prompts and rules as a per team configuration (their story template, their definition of ready).
- Train champions in each tribe; publish a short "good canvas" guide from the pilot's best examples.

## Risks and controls

| Risk | Control |
|---|---|
| Plausible but wrong requirements | Human approval of the canvas; open questions surfaced explicitly |
| Prompt injection through uploaded docs | Documents wrapped as data; agents told to ignore instructions inside them |
| Sensitive data in briefs | Moderation flags personal data; redaction or on premises deployment for regulated teams |
| Quality drift after changes | Golden set scorecard run in CI before every release |
| Cost surprises | Context budget, model routing, per run cost in the log |
