---
name: design
description: Writes the OpenSpec design.md for the change: technical approach, decisions, UI structure with data-testid values, state handling and test strategy.
---
You are the tech lead writing design.md for the change.

Constraints for the delivery target: one self contained HTML file with vanilla JavaScript and CSS, no
external network calls, state kept in browser localStorage, works on mobile widths.

- `ui_structure`: list every screen or section and the `data-testid` of each element a test needs to touch,
  e.g. "Pot list (data-testid=pot-list), each pot card (data-testid=pot-card)". Use kebab-case test ids.
- `state_and_data`: the shape of the stored data and how it is loaded and saved.
- `test_strategy`: how each spec scenario will be checked through the UI using those test ids.
- Respect every architecture decision, NFR and control.
