---
name: build-step
description: Use when Phase 3 planning is complete and it's time to start the build/review loop. Creates an agent team with developer and reviewer teammates. Requires current_phase to be build.
---

# Build Step

## Overview

Phase 4 of the one-shot-build workflow. Create an agent team to implement the epic's steps with a developer/reviewer loop.

## Pre-Conditions

- `kyros-agent-workflow/project-state.yaml` shows `workflow.current_phase: build`
- `workflow.current_epic` and `workflow.current_step` are set
- Tests exist (written during plan-epic phase)
- TDD baseline tag exists

## Process

### Step 1: Read state and plan
Read `kyros-agent-workflow/project-state.yaml` to identify the current epic and its steps.
Read the implementation plan from `kyros-agent-workflow/docs/plans/`.
Read `kyros-agent-workflow/.harnessrc` for project-specific configuration overrides.

### Step 2: Create agent team
Create an agent team with the following structure:

**Team prompt:**
```
We are implementing epic "[epic-name]" for a client analytics project.

The implementation plan is at kyros-agent-workflow/docs/plans/<epic>-plan.md.
The epic spec is at kyros-agent-workflow/docs/epics/<epic>.yaml.
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
- Do NOT modify any test files — they are immutable
- Commit after every step with a descriptive message
- If tests fail, fix the implementation (not the tests)
- Knowledge capture:
  - When you resolve a notable problem (test failure fixed, workaround found, unexpected behavior):
    1. Write a solution doc to kyros-agent-workflow/docs/solutions/<category>/ using the template
    2. Include validated YAML frontmatter (the TaskCompleted hook validates the schema)
    3. Use descriptive filenames: YYYY-MM-DD-brief-description.md
  - When you encounter a problem you can't immediately solve:
    1. Ask the lead to dispatch the learnings-researcher agent
    2. The researcher will search prior solutions for similar issues
    3. Apply any relevant findings before continuing
  - At epic boundaries, you'll be asked: "Is this project-specific or team-wide?"
    - Project-specific → stays in ./kyros-agent-workflow/docs/solutions/
    - Team-wide → will be copied to the shared knowledge repo
- Before marking a step complete, run self-verification:
  bash <plugin_root>/hooks/self-check.sh <step-name> <epic-name> tdd-baseline-<epic>
- Fix any failures before proceeding. Do NOT rely on the TaskCompleted hook to catch these.

Reviewer instructions:
- After the developer completes a step, review the diff
- Check against review criteria in kyros-agent-workflow/docs/standards/review-criteria.md
- Run the full test suite yourself
- Check test immutability (no test files changed since tdd-baseline)
- If changes needed: message the developer directly with specific feedback
- If approved: mark the task as complete
- Verify any new solution docs have valid YAML frontmatter (run validate-solution-doc.sh)
- Flag solution docs that seem universally applicable (not just project-specific)

The lead should:
- Populate the task list with steps from the implementation plan
- Monitor for stuck loops (same error 5+ times = halt)
- Track progress via git changes
- Update kyros-agent-workflow/project-state.yaml after each approved step
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
- Update `kyros-agent-workflow/project-state.yaml`: set `workflow.current_phase: submit`
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
1. Update `kyros-agent-workflow/project-state.yaml` with failure context
2. Log the issue to `kyros-agent-workflow/claude-progress.txt`
3. Tell the user what happened and what was tried
