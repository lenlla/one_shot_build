---
name: plan-epic
description: Use when starting Phase 3 for the current epic. Creates a TDD plan with steps, acceptance criteria, and writes tests FIRST. Tests become immutable during build.
---

# Plan Epic

## Overview

Phase 3 of the one-shot-build workflow. Create a TDD plan for the current epic and write all tests before any implementation.

## Pre-Conditions

- `kyros-agent-workflow/project-state.yaml` shows `workflow.current_phase: plan`
- `workflow.current_epic` is set
- Epic spec exists in `kyros-agent-workflow/docs/epics/`

## Process

### Step 1: Read the epic spec
Read the current epic's YAML from `kyros-agent-workflow/docs/epics/`. Understand the acceptance criteria.

### Step 1.5: Search for relevant prior solutions

Dispatch the **learnings-researcher** subagent with the Task tool:
- Provide: the epic name, component type, list of step names
- Wait for the researcher to return relevant learnings
- Incorporate any critical patterns or known pitfalls into the step breakdown and test design
- If the researcher found solutions for similar problems, reference them in the implementation plan

### Step 2: Break into steps
Break the epic into sequential steps. Each step should be:
- One focused unit of work
- Independently testable
- Has clear acceptance criteria derived from the epic

Present the step breakdown to the user for approval.

### Step 3: Write tests (TDD)
For each step, write the test file FIRST:
- Tests live in `kyros-agent-workflow/tests/` mirroring `kyros-agent-workflow/src/` structure
- Each test tests ONE behavior from the step's acceptance criteria
- Tests should FAIL at this point (no implementation yet)

### Step 4: Run tests to confirm they fail
Run the test suite to confirm all new tests fail as expected:
```bash
pytest kyros-agent-workflow/tests/ -v --tb=short
```
This confirms the tests are correctly written and will catch implementation.

### Step 5: Tag the TDD baseline
Create a git tag so the test-immutability check can reference it:
```bash
git tag tdd-baseline-<epic-name>
```

### Step 6: Write the implementation plan
Create `kyros-agent-workflow/docs/plans/<epic-name>-plan.md` with:
- Step-by-step implementation instructions
- Which files to create/modify for each step
- Expected behavior after each step
- Reference to the test that validates each step

### Step 7: Update state
- Add all steps to `kyros-agent-workflow/project-state.yaml` under the current epic
- Set the first step as `workflow.current_step`
- Set `workflow.current_phase: build`
- Set each step's `tests_pass: false` and `review_approved: false`

### Step 8: Commit and log progress
```bash
git add kyros-agent-workflow/tests/ kyros-agent-workflow/docs/plans/ kyros-agent-workflow/project-state.yaml
git commit -m "test: write TDD tests for epic <name>; plan: add implementation plan"
```

Tell the user: "Tests written and plan created. Run `/build` to start the agent team build/review loop."

## Important
- Tests written here are IMMUTABLE during the build phase.
- The developer agent cannot modify these tests. If tests need to change, the user must return to this phase.
- Write tests that are specific enough to catch correct behavior but not so brittle that correct implementations fail.
