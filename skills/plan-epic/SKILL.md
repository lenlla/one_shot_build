---
name: plan-epic
description: Create a TDD plan for a single epic. Writes tests FIRST (immutable during build), then writes a detailed implementation plan. Called by the execute-plan orchestrator — receives epic spec path and epics directory as context.
---

# Plan Epic

## Overview

Create a TDD plan for a single epic. Write all tests before any implementation. Tests become immutable during the build phase.

## Context (provided by orchestrator)

This skill is invoked by the `execute-plan` orchestrator as a sub-agent. The orchestrator provides:
- **epic_spec_path**: Path to the epic's YAML spec file
- **epics_dir**: Path to the epics directory (for state updates)
- **epic_name**: Name identifier for this epic

## Process

### Step 0: Create epic branch

Switch to a clean branch for this epic's work:
```bash
git checkout main && git pull origin main
git checkout -b epic/<epic-name>
```

If the branch already exists (resumed session):
```bash
git checkout epic/<epic-name>
git pull origin epic/<epic-name> --ff-only
```

### Step 1: Read the epic spec

Read the epic YAML spec from the provided path. Understand the acceptance criteria.

### Step 1.5: Search for relevant prior solutions

Dispatch the **learnings-researcher** subagent with the Task tool:
- Provide: the epic name, component type, list of acceptance criteria
- Wait for the researcher to return relevant learnings
- Incorporate any critical patterns or known pitfalls into the step breakdown and test design

### Step 2: Break into steps

Break the epic into sequential steps. Each step should be:
- One focused unit of work
- Independently testable
- Has clear acceptance criteria derived from the epic

Present the step breakdown. Since this is running as a sub-agent, write the breakdown to a temporary file for the orchestrator to review if in interactive mode.

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

### Step 5: Tag the TDD baseline

```bash
git tag tdd-baseline-<epic-name>
```

### Step 6: Write the implementation plan

Create `kyros-agent-workflow/docs/plans/<epic-name>-plan.md` with the detailed implementation plan. Follow this format:

````markdown
# <Epic Name> Implementation Plan

**Goal:** [One sentence]
**Architecture:** [2-3 sentences]

---

### Task N: [Step Name]

**Files:**
- Create: `kyros-agent-workflow/src/exact/path/to/file.py`
- Test: `kyros-agent-workflow/tests/exact/path/to/test_file.py`

**Substep 1: Run test to verify it fails**
Run: `pytest kyros-agent-workflow/tests/path/test_file.py::test_name -v`
Expected: FAIL with `<specific error>`

**Substep 2: Write minimal implementation**
```python
# exact code here
```

**Substep 3: Run test to verify it passes**
Run: `pytest kyros-agent-workflow/tests/path/test_file.py::test_name -v`
Expected: PASS

**Substep 4: Commit**
```bash
git add <specific files>
git commit -m "feat(<epic>): implement <step>"
```
````

Requirements:
- Exact file paths always
- Complete code (never "add validation here")
- Exact commands with expected output

### Step 7: Commit and report

```bash
git add kyros-agent-workflow/tests/ kyros-agent-workflow/docs/plans/
git commit -m "test: write TDD tests for epic <name>; plan: add implementation plan"
```

Report back to the orchestrator: "Planning complete for epic <name>. Tests written, implementation plan ready."

## Important

- Tests written here are IMMUTABLE during the build phase.
- The developer agent cannot modify these tests.
- Write tests that are specific enough to catch correct behavior but not so brittle that correct implementations fail.
