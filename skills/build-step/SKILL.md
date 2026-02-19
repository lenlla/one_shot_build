---
name: build-step
description: Coordinate the build/review loop for a single epic. Spawns a fresh developer + reviewer sub-agent per step. Called by the execute-plan orchestrator.
---

# Build Step

## Overview

Coordinate implementation of an epic's steps. For each step, spawn a fresh developer sub-agent and reviewer sub-agent via the Task tool. This ensures each agent gets a clean context window focused on one task.

## Context (provided by orchestrator)

This skill is invoked by the `execute-plan` orchestrator as a sub-agent. The orchestrator provides:
- **epic_name**: Name identifier for this epic
- **build_dir**: Path to the build directory (for state updates)
- **plan_path**: Path to the implementation plan (`<build_dir>/plans/<epic>-plan.md`)
- **epic_spec_path**: Path to the epic YAML spec
- **tdd_baseline_tag**: Git tag for test immutability checks (e.g., `tdd-baseline-<epic-name>`)
- **mode**: `interactive` or `autonomous` (determines whether replanning escalation is available)

## Process

### Step 1: Read plan and initialize step state

Read the implementation plan from the provided path.
Read `kyros-agent-workflow/.harnessrc` for project-specific configuration overrides (circuit breaker thresholds, model selection, test commands).
Extract `shared_knowledge_path` from `.harnessrc` if configured. This path will be passed to developer sub-agents so they can search team-level solution docs.

Source `<plugin_root>/lib/state.sh` and call `init_steps_from_plan` to parse the plan and create step entries in `.execution-state.yaml`:

```bash
source <plugin_root>/lib/state.sh
init_steps_from_plan "<build_dir>" "<epic_name>" "<plan_path>"
```

If step entries already exist (resumed session), skip initialization — use the existing state.

### Step 2: Loop through steps

For each step (obtained via `get_next_pending_step`):

#### 2a: Extract step context from plan

Parse the plan file to extract the section for this specific step. The section starts at `### Task N: [Name]` and ends at the next `### Task` heading or end of file. This section contains:
- Files to create/modify
- Test file paths
- Substep instructions
- Expected test commands and output

#### 2b: Update state

```bash
update_step_status "<build_dir>" "<epic_name>" "<step_name>" "in_progress"
```

#### 2c: Dispatch developer sub-agent

Dispatch a **developer sub-agent** with the Task tool:

**Prompt:**
```
You are implementing a single step of epic "<epic_name>" for a client analytics project.

## Your Task

<paste the extracted step section from the plan>

## Context Files (read these first)

- Coding standards: kyros-agent-workflow/docs/standards/coding-standards.md
- Epic spec: <epic_spec_path>
- TDD baseline tag: <tdd_baseline_tag>
- Project solutions: kyros-agent-workflow/docs/solutions/
- Team solutions: <shared_knowledge_path>/docs/solutions/ (if configured in .harnessrc)

## Rules

- Do NOT modify any test files — they are immutable (baseline: <tdd_baseline_tag>)
- If tests fail, fix the implementation (not the tests)
- Run the test command after implementing to verify tests pass
- Commit with a descriptive message: "feat(<epic_name>): implement <step description>"
- Before finishing, run self-verification:
  bash <plugin_root>/hooks/self-check.sh <step_name> <epic_name> <tdd_baseline_tag>
- Knowledge capture: if you resolve a notable problem, write a solution doc to
  kyros-agent-workflow/docs/solutions/<category>/ with validated YAML frontmatter
- Read any solution docs listed under "Relevant Solutions" in your task section — these
  were selected during planning as directly applicable to this step. Also search
  kyros-agent-workflow/docs/solutions/ for additional patterns matching this step's
  component type, data characteristics, or error patterns. Apply relevant patterns
  proactively — don't wait until you're stuck.

## When Done

Report back with:
- FILES_MODIFIED: <list of files changed>
- TESTS: PASS or FAIL (with output if FAIL)
- COMMITS: <commit hash and message>
```

Wait for the developer sub-agent to complete.

**If developer reports TESTS: FAIL** and has exhausted self-debugging (3 attempts with no progress): proceed to reviewer anyway — the reviewer will flag the failure and provide specific feedback for a retry.

#### 2d: Dispatch reviewer sub-agent

Dispatch a **reviewer sub-agent** with the Task tool:

**Prompt:**
```
You are reviewing a single step of epic "<epic_name>" for a client analytics project.

## What to Review

Run `git diff <tdd_baseline_tag>..HEAD -- . ':!*.test.*' ':!*test_*'` to see implementation changes.
Run `git diff HEAD~1..HEAD` to see just this step's changes.

## Review Criteria

Read: kyros-agent-workflow/docs/standards/review-criteria.md

## Checks

1. Run the full test suite yourself: <test_command from .harnessrc or default>
2. Verify test immutability: no test files changed since <tdd_baseline_tag>
   Run: `git diff <tdd_baseline_tag> -- kyros-agent-workflow/tests/`
   Expected: empty output
3. Check against review criteria
4. Verify any new solution docs have valid YAML frontmatter

## Your Response

If APPROVED:
  REVIEW: APPROVED
  SUMMARY: <one-line summary of what was implemented correctly>

If CHANGES REQUESTED:
  REVIEW: CHANGES_REQUESTED
  ISSUES:
  - FILE: <file path>
    LINE: <line number>
    CRITERION: <which review criterion failed>
    PROBLEM: <what's wrong>
    FIX: <specific fix needed>
```

Wait for the reviewer sub-agent to complete.

#### 2e: Handle review result

**If APPROVED:**
- Update state: `update_step_status "<build_dir>" "<epic_name>" "<step_name>" "completed"`
- Log progress: `log_progress "<build_dir>" "Step <step_name> approved by reviewer"`
- Continue to the next step

**If CHANGES_REQUESTED:**
- Increment review rounds: `increment_review_rounds "<build_dir>" "<epic_name>" "<step_name>"`
- Check if review rounds exceed threshold (default 5 from `.harnessrc`):
  - **If exceeded:** Trigger circuit breaker (see below)
  - **If not exceeded:** Dispatch a **new developer sub-agent** with the reviewer's feedback:

    ```
    You are fixing review feedback for step "<step_name>" of epic "<epic_name>".

    ## Reviewer Feedback

    <paste the reviewer's ISSUES list>

    ## Rules

    - Fix ONLY the issues flagged by the reviewer
    - Do NOT modify test files (baseline: <tdd_baseline_tag>)
    - Run tests after fixing
    - Commit: "fix(<epic_name>): address review feedback for <step_name>"
    - If the reviewer's feedback relates to a known pattern (data quality, type handling,
      performance, etc.), check kyros-agent-workflow/docs/solutions/ for existing solutions
      before implementing your fix.
    ```

    Then dispatch the reviewer again (step 2d). This is the review loop for a single step.

### Step 3: Circuit breaker monitoring

Track across the step loop:

| Signal | Threshold | Action |
|--------|-----------|--------|
| No file changes after developer dispatch | 3 consecutive dispatches | Log warning, include in next developer prompt: "Your previous attempts produced no file changes. Try a fundamentally different approach." |
| Same error repeated | 5 times across dispatches | Halt. Trigger replanning escalation (see Step 4) or report to orchestrator. |
| Review rounds exceeded | 5 rounds for a single step | Halt. Trigger replanning escalation (see Step 4) or report to orchestrator. |

When halting without replanning:
1. Log the issue: `log_progress "<build_dir>" "CIRCUIT BREAKER: <signal> for step <step_name>"`
2. Report the failure context to the orchestrator

### Step 4: Replanning escalation (autonomous mode only)

When the circuit breaker trips due to persistent test failures (same error repeated, or review rounds exceeded where the core issue is that the tests themselves appear wrong), and the execution mode is `autonomous`:

Dispatch a **replanning sub-agent** with the Task tool:

**Prompt:**
```
You are a replanning agent for epic "<epic_name>". The build has stalled on step "<step_name>".

## Problem

The developer agent has been unable to pass the tests for this step after multiple attempts.
The circuit breaker tripped due to: <reason>

## Error Context

<paste the last developer's test output and the last reviewer's feedback>

## Your Job

Analyze whether the tests are genuinely wrong. Tests may be wrong if:
- They test behavior that contradicts the epic's acceptance criteria
- They assume an implementation approach that is impossible given the data/dependencies
- They have a logic error (off-by-one, wrong assertion, wrong fixture)
- They assume step N would be implemented a certain way, but the actual implementation took a different valid approach

If the tests ARE correct and the implementation is simply difficult:
  VERDICT: TESTS_CORRECT
  SUGGESTION: <suggest a different implementation approach for the developer>

If the tests are WRONG and need modification:
  VERDICT: TESTS_WRONG
  CHANGES:
  - FILE: <test file path>
    CURRENT: <the problematic test code>
    PROPOSED: <the corrected test code>
    JUSTIFICATION: <why this change is necessary, referencing the epic's acceptance criteria>

## Rules

- You are NOT the developer. Do not write implementation code.
- Only propose test changes that are clearly justified by the epic spec.
- Never weaken test coverage — only correct wrong assertions.
- Read the epic spec at <epic_spec_path> to verify your reasoning.
```

**Handle replanning result:**

**If VERDICT: TESTS_CORRECT:**
- Dispatch a new developer sub-agent with the replanning agent's suggested approach
- Resume the review loop (one more attempt before halting for good)
- If this attempt also fails, halt and report to orchestrator

**If VERDICT: TESTS_WRONG:**
- Apply the proposed test changes
- Create a new TDD baseline tag: `tdd-baseline-<epic-name>-v<N>` (increment N)
- Update the `tdd_baseline_tag` used by subsequent developer/reviewer agents
- Log prominently: `log_progress "<build_dir>" "REPLAN: Tests modified for step <step_name>. New baseline: <new_tag>. Justification: <summary>"`
- Commit: `git commit -m "fix(<epic_name>): correct tests for <step_name> per replanning agent"`
- Resume building from the current step with the corrected tests

**Replanning limit:** Only one replanning escalation per step. If the replanning agent's fix doesn't resolve the issue, halt and report to the orchestrator.

### Step 5: After all steps complete

When `get_next_pending_step` returns empty (all steps completed):
- Log: `log_progress "<build_dir>" "Epic <epic_name> build complete. All steps pass tests + review."`
- Report back to the orchestrator: "Build complete for epic <epic_name>. All steps implemented and reviewed."
