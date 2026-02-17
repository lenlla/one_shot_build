---
name: harness-status
description: Use when the user wants to check the current workflow state, see which phase/epic/step they're on, and what to do next.
---

# Harness Status

## Overview

Display the current workflow state from `project-state.yaml` and suggest the next action.

## Process

1. **Read state file** — Read `project-state.yaml` from the project root
2. **Display current position** — Show: phase, epic, step
3. **Show gate status** — For the current step: tests_pass, review_approved
4. **Show epic progress** — How many steps completed vs total for current epic
5. **Show overall progress** — How many epics completed vs total
6. **Suggest next action** — Based on current phase, tell the user what command to run

## Output Format

```
## Workflow Status

**Phase:** [current_phase]
**Epic:** [current_epic] ([completed_steps]/[total_steps] steps)
**Step:** [current_step]

### Gates
- Tests: [pass/fail/pending]
- Review: [approved/changes_requested/pending]

### Epic Progress
- [x] step-01-name (completed)
- [x] step-02-name (completed)
- [ ] step-03-name (in progress) <-- current
- [ ] step-04-name (pending)

### Overall
[completed_epics]/[total_epics] epics complete

### Next Action
Run `/command` to [do the next thing].
```

## Edge Cases

- If no `project-state.yaml` exists: tell the user to run `/init`
- If all epics are complete: congratulate and suggest final review
- If circuit breaker is OPEN: warn and show the failure context
