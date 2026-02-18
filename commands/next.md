---
description: "Advance to the next step in the workflow based on current state."
disable-model-invocation: true
---

Read kyros-agent-workflow/project-state.yaml and determine the current phase. Then invoke the appropriate one-shot-build skill:
- If current_phase is gather_context: invoke one-shot-build:gather-context
- If current_phase is define_epics: invoke one-shot-build:define-epics
- If current_phase is plan: invoke one-shot-build:plan-epic
- If current_phase is build: invoke one-shot-build:build-step
- If current_phase is submit: invoke one-shot-build:submit-epic
- If current_phase is done: tell the user all epics are complete

Follow the invoked skill exactly as presented to you.
