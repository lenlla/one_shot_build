---
name: build-step
description: Use when Phase 3 planning is complete and it's time to start the build/review loop. Creates an agent team with developer and reviewer teammates. Requires current_phase to be build.
---

# Build Step

## Overview

Phase 4 of the one-shot-build workflow. Create an agent team to implement the epic's steps with a developer/reviewer loop.

## Pre-Conditions

- `project-state.yaml` shows `workflow.current_phase: build`
- `workflow.current_epic` and `workflow.current_step` are set
- Tests exist (written during plan-epic phase)
- TDD baseline tag exists

## Process

### Step 1: Read state and plan
Read `project-state.yaml` to identify the current epic and its steps.
Read the implementation plan from `docs/plans/`.
Read `.harnessrc` for project-specific configuration overrides.

### Step 2: Create agent team
Create an agent team with the following structure:

**Team prompt:**
```
We are implementing epic "[epic-name]" for a client analytics project.

The implementation plan is at docs/plans/<epic>-plan.md.
The epic spec is at docs/epics/<epic>.yaml.
Coding standards are at docs/standards/coding-standards.md.
Review criteria are at docs/standards/review-criteria.md.

Spawn two teammates:
1. A developer teammate to implement the steps
2. A reviewer teammate to review each completed step

Use delegate mode — I (the lead) will only coordinate, not write code.

Developer instructions:
- Work through steps one at a time from the task list
- For each step: implement, run tests, self-review, commit
- After completing a step, emit a structured status block:
  STATUS: COMPLETE
  TASKS_COMPLETED: <n>
  FILES_MODIFIED: <n>
  TESTS: PASS | FAIL
  WORK_TYPE: implementation
  EXIT_SIGNAL: false
- Do NOT modify any test files — they are immutable
- Commit after every step with a descriptive message
- If tests fail, fix the implementation (not the tests)

Reviewer instructions:
- After the developer completes a step, review the diff
- Check against review criteria in docs/standards/review-criteria.md
- Run the full test suite yourself
- Check test immutability (no test files changed since tdd-baseline)
- If changes needed: message the developer directly with specific feedback
- If approved: mark the task as complete

The lead should:
- Populate the task list with steps from the implementation plan
- Monitor for stuck loops (same error 5+ times = halt)
- Track progress via git changes
- Update project-state.yaml after each approved step
```

### Step 3: Switch to delegate mode
Press Shift+Tab to enter delegate mode (coordination only, no code).

### Step 4: Monitor the loop
Watch for:
- **Circuit breaker signals:** No file changes for 3+ iterations, same error 5+ times
- **Stuck loops:** Developer repeating the same approach without progress
- **Review cycles:** If review exceeds 5 rounds, halt and escalate to human

### Step 5: After all steps complete
When all steps in the epic are complete:
- Update `project-state.yaml`: set `workflow.current_phase: submit`
- Log progress: "Epic [name] build complete. All steps pass tests + review."
- Clean up the agent team
- Tell the user: "Build complete. Run `/submit` to create a PR for this epic."

## Circuit Breaker Behavior

| Signal | Threshold | Action |
|--------|-----------|--------|
| No file changes | 3 iterations | Warn developer, suggest different approach |
| Same error repeated | 5 times | Halt. Message: "Stuck loop detected. Escalating to human." |
| Review rounds exceeded | 5 rounds | Halt. Message: "Review loop exceeded. Escalating to human." |
| Permission denial | 2 times | Halt. Check permissions. |

When halting:
1. Update `project-state.yaml` with failure context
2. Log the issue to `claude-progress.txt`
3. Tell the user what happened and what was tried
