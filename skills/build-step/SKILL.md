---
name: build-step
description: Run the agent team build/review loop for a single epic. Creates developer + reviewer sub-agents. Called by the execute-plan orchestrator — receives epic context as parameters.
---

# Build Step

## Overview

Create an agent team to implement the epic's steps with a developer/reviewer loop.

## Context (provided by orchestrator)

This skill is invoked by the `execute-plan` orchestrator as a sub-agent. The orchestrator provides:
- **epic_name**: Name identifier for this epic
- **epics_dir**: Path to the epics directory (for state updates)
- **plan_path**: Path to the implementation plan (`kyros-agent-workflow/docs/plans/<epic>-plan.md`)
- **epic_spec_path**: Path to the epic YAML spec
- **tdd_baseline_tag**: Git tag for test immutability checks (e.g., `tdd-baseline-<epic-name>`)

## Process

### Step 1: Read plan and configuration

Read the implementation plan from the provided path.
Read `kyros-agent-workflow/.harnessrc` for project-specific configuration overrides (circuit breaker thresholds, model selection, test commands).

### Step 2: Create agent team

Create an agent team with the following structure:

**Team prompt:**
```
We are implementing epic "[epic-name]" for a client analytics project.

The implementation plan is at <plan_path>.
The epic spec is at <epic_spec_path>.
Coding standards are at kyros-agent-workflow/docs/standards/coding-standards.md.
Review criteria are at kyros-agent-workflow/docs/standards/review-criteria.md.

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
- Do NOT modify any test files — they are immutable (baseline: <tdd_baseline_tag>)
- Commit after every step with a descriptive message
- If tests fail, fix the implementation (not the tests)
- Knowledge capture:
  - When you resolve a notable problem, write a solution doc to kyros-agent-workflow/docs/solutions/<category>/
  - Include validated YAML frontmatter
  - Use descriptive filenames: YYYY-MM-DD-brief-description.md
- Before marking a step complete, run self-verification:
  bash <plugin_root>/hooks/self-check.sh <step-name> <epic-name> <tdd_baseline_tag>
- Fix any failures before proceeding

Reviewer instructions:
- After the developer completes a step, review the diff
- Check against review criteria in kyros-agent-workflow/docs/standards/review-criteria.md
- Run the full test suite yourself
- Check test immutability (no test files changed since <tdd_baseline_tag>)
- If changes needed: message the developer directly with specific feedback
- If approved: mark the task as complete
- Verify any new solution docs have valid YAML frontmatter
```

### Step 3: Switch to delegate mode

Press Shift+Tab to enter delegate mode (coordination only, no code).

### Step 4: Monitor the loop

Watch for:
- **Circuit breaker signals:** No file changes for 3+ iterations, same error 5+ times
- **Stuck loops:** Developer repeating the same approach without progress
- **Review cycles:** If review exceeds 5 rounds, halt and escalate

### Step 5: After all steps complete

When all steps in the epic are complete:
- Log progress: "Epic [name] build complete. All steps pass tests + review."
- Clean up the agent team
- Report back to the orchestrator: "Build complete for epic <name>. All steps implemented and reviewed."

## Circuit Breaker Behavior

| Signal | Threshold | Action |
|--------|-----------|--------|
| No file changes | 3 iterations | Warn developer, suggest different approach |
| Same error repeated | 5 times | Halt. Report to orchestrator: "Stuck loop detected." |
| Review rounds exceeded | 5 rounds | Halt. Report to orchestrator: "Review loop exceeded." |
| Permission denial | 2 times | Halt. Check permissions. |

When halting:
1. Log the issue to `kyros-agent-workflow/claude-progress.txt`
2. Report the failure context to the orchestrator (which will surface it to the user)
