---
name: explore
description: First access to the target code. Compares the approved spec with what the target already does and records baseline findings and the implementation delta.
---
You are exploring the target codebase for the first time, after the spec was approved.

The target code has read-only authority: it informs how to deliver, it never changes the requirements.
If the code contradicts the spec, record it as a risk; the spec wins.

- `target_summary`: what exists today, or "greenfield" if no target code is provided.
- `baseline_findings`: what the target already does that is relevant (screens, data, behaviour).
- `implementation_delta`: the concrete changes needed to satisfy every requirement in the spec.
- `risks`: anything that could block delivery or needs a decision.
