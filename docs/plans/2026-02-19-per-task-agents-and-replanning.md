# Per-Task Agents, Step-Level State, and Replanning Escalation

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the per-epic agent team with per-task (per-step) developer/reviewer agents, add step-level tracking to `.execution-state.yaml`, and add a replanning escalation path for autonomous mode when tests are genuinely wrong.

**Architecture:** The build-step skill becomes a coordinator that loops through steps, spawning a fresh developer sub-agent and reviewer sub-agent for each step via the Task tool. Step-level progress is persisted in `.execution-state.yaml` so sessions can resume at the step level. When the circuit breaker trips due to persistent test failures, the coordinator can dispatch a replanning agent that analyzes the situation and proposes test changes with a new TDD baseline tag.

**Tech Stack:** Bash (state library, hooks), Markdown (skills, docs), BATS (tests), yq (YAML manipulation)

---

### Task 1: Add step-level state functions to lib/state.sh

**Files:**
- Modify: `lib/state.sh:25-143`
- Test: `tests/state_test.bats`

The execution state YAML will expand from epic-level only to include step-level tracking:

```yaml
epics:
  data-loading:
    status: building
    current_step: "step-02-validate-schema"
    tdd_baseline_tag: "tdd-baseline-data-loading"
    steps:
      step-01-load-csv:
        status: completed
        review_rounds: 1
        completed_at: "2026-02-19T10:00:00Z"
      step-02-validate-schema:
        status: in_progress
        review_rounds: 2
      step-03-type-casting:
        status: pending
```

**Step 1: Write the failing tests**

Add these tests to `tests/state_test.bats` after the existing `execution_summary` test (after line 137):

```bash
# --- step-level state tests ---

@test "read_step_status returns empty when no steps exist" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
YAML
    run read_step_status "$TEST_DIR/epics/v1" "data-loading" "step-01"
    assert_success
    assert_output ""
}

@test "read_step_status returns step status" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    steps:
      step-01:
        status: completed
      step-02:
        status: in_progress
YAML
    run read_step_status "$TEST_DIR/epics/v1" "data-loading" "step-01"
    assert_success
    assert_output "completed"
}

@test "update_step_status sets step status" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    steps:
      step-01:
        status: pending
YAML
    run update_step_status "$TEST_DIR/epics/v1" "data-loading" "step-01" "in_progress"
    assert_success

    run read_step_status "$TEST_DIR/epics/v1" "data-loading" "step-01"
    assert_output "in_progress"
}

@test "init_steps_from_plan creates step entries from plan headings" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
YAML
    # Create a mock plan file
    mkdir -p "$TEST_DIR/kyros-agent-workflow/docs/plans"
    cat > "$TEST_DIR/kyros-agent-workflow/docs/plans/data-loading-plan.md" <<'PLAN'
# Data Loading Implementation Plan

**Goal:** Load CSV files
**Architecture:** Simple pandas loader

---

### Task 1: Load CSV

**Files:**
- Create: `src/loader.py`

### Task 2: Validate Schema

**Files:**
- Create: `src/validator.py`

### Task 3: Type Casting

**Files:**
- Create: `src/caster.py`
PLAN
    run init_steps_from_plan "$TEST_DIR/epics/v1" "data-loading" "$TEST_DIR/kyros-agent-workflow/docs/plans/data-loading-plan.md"
    assert_success

    run read_step_status "$TEST_DIR/epics/v1" "data-loading" "task-1-load-csv"
    assert_output "pending"

    run read_step_status "$TEST_DIR/epics/v1" "data-loading" "task-2-validate-schema"
    assert_output "pending"

    run read_step_status "$TEST_DIR/epics/v1" "data-loading" "task-3-type-casting"
    assert_output "pending"
}

@test "get_next_pending_step returns first non-completed step" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    steps:
      task-1-load-csv:
        status: completed
      task-2-validate-schema:
        status: pending
      task-3-type-casting:
        status: pending
YAML
    run get_next_pending_step "$TEST_DIR/epics/v1" "data-loading"
    assert_success
    assert_output "task-2-validate-schema"
}

@test "get_next_pending_step returns empty when all steps completed" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    steps:
      task-1-load-csv:
        status: completed
      task-2-validate-schema:
        status: completed
YAML
    run get_next_pending_step "$TEST_DIR/epics/v1" "data-loading"
    assert_success
    assert_output ""
}

@test "increment_review_rounds tracks review count" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    steps:
      step-01:
        status: in_progress
        review_rounds: 1
YAML
    run increment_review_rounds "$TEST_DIR/epics/v1" "data-loading" "step-01"
    assert_success

    run read_execution_state "$TEST_DIR/epics/v1" 'epics.data-loading.steps.step-01.review_rounds'
    assert_output "2"
}

@test "execution_summary includes step progress" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    current_step: "task-2-validate-schema"
    steps:
      task-1-load-csv:
        status: completed
      task-2-validate-schema:
        status: in_progress
      task-3-type-casting:
        status: pending
YAML

    run execution_summary "$TEST_DIR/epics/v1"
    assert_success
    assert_output --partial "step 1/3"
}
```

**Step 2: Run tests to verify they fail**

Run: `bats tests/state_test.bats`
Expected: New tests fail (functions don't exist yet), existing tests still pass.

**Step 3: Implement the step-level state functions**

Add the following functions to `lib/state.sh`, after the existing `execution_summary` function (after line 143):

```bash
# --- Step-level state operations ---

# Read the status of a specific step within an epic
# Usage: read_step_status "/path/to/epics/v1" "data-loading" "step-01"
read_step_status() {
    local epics_dir="$1"
    local epic_name="$2"
    local step_name="$3"
    read_execution_state "$epics_dir" "epics.\"${epic_name}\".steps.\"${step_name}\".status"
}

# Update the status of a specific step within an epic
# Usage: update_step_status "/path/to/epics/v1" "data-loading" "step-01" "completed"
update_step_status() {
    local epics_dir="$1"
    local epic_name="$2"
    local step_name="$3"
    local status="$4"
    update_execution_state "$epics_dir" "epics.\"${epic_name}\".steps.\"${step_name}\".status" "$status"
    # Also update current_step pointer
    if [[ "$status" == "in_progress" ]]; then
        update_execution_state "$epics_dir" "epics.\"${epic_name}\".current_step" "$step_name"
    fi
}

# Parse implementation plan and initialize step entries in execution state
# Usage: init_steps_from_plan "/path/to/epics/v1" "data-loading" "/path/to/plan.md"
init_steps_from_plan() {
    local epics_dir="$1"
    local epic_name="$2"
    local plan_path="$3"
    local state_file
    state_file=$(execution_state_file "$epics_dir")

    if [[ ! -f "$plan_path" ]]; then
        echo "Error: Plan file not found at $plan_path" >&2
        return 1
    fi

    # Extract task headings: "### Task N: [Name]" -> "task-n-name-slug"
    local step_names
    step_names=$(grep -E '^### Task [0-9]+:' "$plan_path" | sed -E 's/^### Task ([0-9]+): (.*)$/\1 \2/' | while read -r num name; do
        # Convert to slug: lowercase, spaces to dashes, strip non-alphanumeric
        local slug
        slug=$(echo "$name" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9 ]//g' | tr ' ' '-' | sed 's/--*/-/g' | sed 's/-$//')
        echo "task-${num}-${slug}"
    done)

    if [[ -z "$step_names" ]]; then
        echo "Error: No task headings found in plan at $plan_path" >&2
        return 1
    fi

    # Create step entries in the execution state
    while IFS= read -r step_name; do
        yq eval -i ".epics.\"${epic_name}\".steps.\"${step_name}\".status = \"pending\"" "$state_file"
    done <<< "$step_names"
}

# Get the next pending step for an epic
# Usage: get_next_pending_step "/path/to/epics/v1" "data-loading"
get_next_pending_step() {
    local epics_dir="$1"
    local epic_name="$2"
    local state_file
    state_file=$(execution_state_file "$epics_dir")

    if [[ ! -f "$state_file" ]]; then
        echo ""
        return 0
    fi

    yq eval ".epics.\"${epic_name}\".steps | to_entries | .[] | select(.value.status != \"completed\") | .key" "$state_file" 2>/dev/null | head -1
}

# Increment the review round counter for a step
# Usage: increment_review_rounds "/path/to/epics/v1" "data-loading" "step-01"
increment_review_rounds() {
    local epics_dir="$1"
    local epic_name="$2"
    local step_name="$3"
    local state_file
    state_file=$(execution_state_file "$epics_dir")

    local current
    current=$(yq eval ".epics.\"${epic_name}\".steps.\"${step_name}\".review_rounds // 0" "$state_file" 2>/dev/null)
    local next=$((current + 1))
    yq eval -i ".epics.\"${epic_name}\".steps.\"${step_name}\".review_rounds = ${next}" "$state_file"
}
```

Also update the `execution_summary` function (lines 115-143) to include step-level detail. Replace the body of the function with logic that also reads step counts:

```bash
execution_summary() {
    local epics_dir="$1"
    local state_file
    state_file=$(execution_state_file "$epics_dir")

    if [[ ! -f "$state_file" ]]; then
        echo "No execution state found"
        return 0
    fi

    local total completed current_epic current_status
    total=$(yq eval '.epics | length' "$state_file" 2>/dev/null || echo "0")
    completed=$(yq eval '.epics | to_entries | .[] | select(.value.status == "completed") | .key' "$state_file" 2>/dev/null | wc -l | tr -d ' ')
    current_epic=$(yq eval '.epics | to_entries | .[] | select(.value.status != "completed" and .value.status != "pending") | .key' "$state_file" 2>/dev/null | head -1)

    if [[ -n "$current_epic" ]]; then
        current_status=$(yq eval ".epics.\"${current_epic}\".status" "$state_file" 2>/dev/null || echo "")

        # Check for step-level tracking
        local steps_total steps_completed
        steps_total=$(yq eval ".epics.\"${current_epic}\".steps | length" "$state_file" 2>/dev/null || echo "0")
        steps_completed=$(yq eval ".epics.\"${current_epic}\".steps | to_entries | .[] | select(.value.status == \"completed\") | .key" "$state_file" 2>/dev/null | wc -l | tr -d ' ')

        if [[ "$steps_total" -gt 0 ]]; then
            echo "${completed}/${total} epics done, currently on '${current_epic}' step ${steps_completed}/${steps_total}"
        else
            echo "${completed}/${total} epics done, currently on '${current_epic}' (${current_status})"
        fi
    else
        echo "${completed}/${total} epics done"
    fi
}
```

**Step 4: Run tests to verify they pass**

Run: `bats tests/state_test.bats`
Expected: All tests pass (existing + new).

**Step 5: Commit**

```bash
git add lib/state.sh tests/state_test.bats
git commit -m "feat: add step-level state tracking to lib/state.sh"
```

---

### Task 2: Rewrite build-step skill for per-task agents

**Files:**
- Rewrite: `skills/build-step/SKILL.md` (complete replacement)

This is the core architectural change. The build-step skill drops the agent team/delegate mode pattern and becomes a coordinator that spawns per-step developer and reviewer sub-agents.

**Step 1: Read the current file**

Read `skills/build-step/SKILL.md` to confirm the current content matches what's in the plan.

**Step 2: Write the new build-step skill**

Replace the entire content of `skills/build-step/SKILL.md` with:

````markdown
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
- **epics_dir**: Path to the epics directory (for state updates)
- **plan_path**: Path to the implementation plan (`kyros-agent-workflow/docs/plans/<epic>-plan.md`)
- **epic_spec_path**: Path to the epic YAML spec
- **tdd_baseline_tag**: Git tag for test immutability checks (e.g., `tdd-baseline-<epic-name>`)

## Process

### Step 1: Read plan and initialize step state

Read the implementation plan from the provided path.
Read `kyros-agent-workflow/.harnessrc` for project-specific configuration overrides (circuit breaker thresholds, model selection, test commands).

Source `<plugin_root>/lib/state.sh` and call `init_steps_from_plan` to parse the plan and create step entries in `.execution-state.yaml`:

```bash
source <plugin_root>/lib/state.sh
init_steps_from_plan "<epics_dir>" "<epic_name>" "<plan_path>"
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
update_step_status "<epics_dir>" "<epic_name>" "<step_name>" "in_progress"
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

## Rules

- Do NOT modify any test files — they are immutable (baseline: <tdd_baseline_tag>)
- If tests fail, fix the implementation (not the tests)
- Run the test command after implementing to verify tests pass
- Commit with a descriptive message: "feat(<epic_name>): implement <step description>"
- Before finishing, run self-verification:
  bash <plugin_root>/hooks/self-check.sh <step_name> <epic_name> <tdd_baseline_tag>
- Knowledge capture: if you resolve a notable problem, write a solution doc to
  kyros-agent-workflow/docs/solutions/<category>/ with validated YAML frontmatter

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
- Update state: `update_step_status "<epics_dir>" "<epic_name>" "<step_name>" "completed"`
- Log progress: `log_progress "<epics_dir>" "Step <step_name> approved by reviewer"`
- Continue to the next step

**If CHANGES_REQUESTED:**
- Increment review rounds: `increment_review_rounds "<epics_dir>" "<epic_name>" "<step_name>"`
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
1. Log the issue: `log_progress "<epics_dir>" "CIRCUIT BREAKER: <signal> for step <step_name>"`
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
- Log prominently: `log_progress "<epics_dir>" "REPLAN: Tests modified for step <step_name>. New baseline: <new_tag>. Justification: <summary>"`
- Commit: `git commit -m "fix(<epic_name>): correct tests for <step_name> per replanning agent"`
- Resume building from the current step with the corrected tests

**Replanning limit:** Only one replanning escalation per step. If the replanning agent's fix doesn't resolve the issue, halt and report to the orchestrator.

### Step 5: After all steps complete

When `get_next_pending_step` returns empty (all steps completed):
- Log: `log_progress "<epics_dir>" "Epic <epic_name> build complete. All steps pass tests + review."`
- Report back to the orchestrator: "Build complete for epic <epic_name>. All steps implemented and reviewed."
````

**Step 3: Verify the skill reads correctly**

Read back `skills/build-step/SKILL.md` and confirm it's well-formed markdown with no formatting issues.

**Step 4: Commit**

```bash
git add skills/build-step/SKILL.md
git commit -m "feat: rewrite build-step skill for per-task agents with replanning escalation"
```

---

### Task 3: Update execute-plan skill for step-level resume

**Files:**
- Modify: `skills/execute-plan/SKILL.md:86-97` (initial state creation)
- Modify: `skills/execute-plan/SKILL.md:125-143` (Phase B)

**Step 1: Read the current file**

Read `skills/execute-plan/SKILL.md` to confirm current content.

**Step 2: Update initial state creation (Step 5 of startup)**

In the section "If not exists (or starting fresh)" (around line 86-97), the initial `.execution-state.yaml` stays the same — steps are NOT populated here. They are populated by `build-step` when it reads the plan in Phase B. This is because steps don't exist until after Phase A (planning) creates the implementation plan.

No change needed to the initial state creation.

**Step 3: Update Phase B to pass execution mode**

In Phase B (around line 125-143), update the build-step dispatch to also pass the execution mode so the build-step coordinator knows whether replanning escalation is available:

Replace the Phase B section with:

```markdown
### Phase B: Build Epic

Update state: set epic status to `building`.

Dispatch a **sub-agent** with the Task tool:
- Prompt: Invoke the build-step skill with context:
  - epic_name: `<epic-name>`
  - epics_dir: `<epics_dir>`
  - plan_path: `kyros-agent-workflow/docs/plans/<epic-name>-plan.md`
  - epic_spec_path: `<epics_dir>/<epic-file>`
  - tdd_baseline_tag: `tdd-baseline-<epic-name>`
  - mode: `<interactive|autonomous>`
- Wait for completion

Monitor the sub-agent's response for circuit breaker trips. If a halt is reported:
- Update state with failure context
- **Both modes:** Surface the issue to the user. "Build halted for '<epic-name>': <reason>. What would you like to do?"
- Stop the loop until the user intervenes

When sub-agent returns successfully, update state: set epic status to `submitting`.
```

**Step 4: Update resume logic for step-level awareness**

In Step 5 of the startup sequence (around line 73-97), update the resume display to show step-level progress when available. After the `execution_summary` call, add:

```markdown
If the resumed epic is in `building` status and has step-level state, also show:
"Step progress for '<epic-name>':
- task-1-load-csv: completed
- task-2-validate-schema: in_progress (review round 2)
- task-3-type-casting: pending

The build will resume from '<next-pending-step>'."
```

**Step 5: Commit**

```bash
git add skills/execute-plan/SKILL.md
git commit -m "feat: update execute-plan to pass mode to build-step and show step-level resume"
```

---

### Task 4: Update harness-status skill for step-level display

**Files:**
- Modify: `skills/harness-status/SKILL.md:33-52` (Active Executions output)

**Step 1: Read the current file**

Read `skills/harness-status/SKILL.md` to confirm current content.

**Step 2: Update the Active Executions output**

Replace the "Output: Active Executions Found" section with:

````markdown
## Output: Active Executions Found

For each execution state found, call `execution_summary` and display:

```
## Workflow Status

### Active Executions

**`<epics-dir>`** — <summary from execution_summary>

| Epic | Status | Steps |
|------|--------|-------|
| data-loading | completed | 3/3 |
| transformation | building | 1/3 (task-2-validate-schema in review round 2) |
| reporting | pending | — |

### Next Action
Run `/execute-plan <epics-dir>` to resume.
```

For epics in `building` status that have step-level state, show step detail:
- Count of completed vs total steps
- Name of current step and its review round count (if > 0)

If multiple execution states exist, show all of them with their summaries.
````

**Step 3: Commit**

```bash
git add skills/harness-status/SKILL.md
git commit -m "feat: update harness-status to display step-level progress"
```

---

### Task 5: Update user guide — Phase B description

**Files:**
- Modify: `docs/user-guide.md:153-207` (Phase B: Build section)

**Step 1: Read the current file**

Read `docs/user-guide.md` lines 150-210 to confirm the Phase B section.

**Step 2: Replace the Phase B section**

Replace everything from `#### Phase B: Build` up to (but not including) `#### Phase C: Submit` with:

````markdown
#### Phase B: Build

The orchestrator dispatches a **build-step coordinator** that manages the implementation of all steps within the epic. Unlike the planning and submit phases, the build phase spawns multiple sub-agents — a fresh developer and reviewer for each step.

**Per-step agent cycle:**

For each step in the implementation plan, the coordinator:

1. **Extracts the step context** from the plan file — the specific section with files, test commands, and implementation instructions
2. **Dispatches a developer sub-agent** with just that step's context, coding standards, and the TDD baseline tag. The developer implements the code, runs tests, self-reviews, and commits.
3. **Dispatches a reviewer sub-agent** with the git diff for that step, review criteria, and acceptance criteria. The reviewer runs the test suite, checks test immutability, and evaluates the diff.

```
Coordinator (build-step)
    |
    +- Step 1 ─── Developer ─── Reviewer ─── Approved ✓
    |              (torn down)   (torn down)
    |
    +- Step 2 ─── Developer ─── Reviewer ─── Changes requested
    |              (torn down)   (torn down)
    |                  |
    |              New Developer ── Reviewer ─── Approved ✓
    |              (torn down)      (torn down)
    |
    +- Step 3 ─── Developer ─── Reviewer ─── Approved ✓
    |              (torn down)   (torn down)
    ...
```

Each developer and reviewer agent gets a **clean context window** focused entirely on one step. This prevents context saturation on large epics — the developer working on step 5 isn't burdened by the accumulated context of steps 1-4.

**The review loop:**

When the reviewer requests changes, the coordinator spawns a **new developer agent** with the reviewer's specific feedback. The new developer has a fresh context containing only the step instructions and the feedback — no accumulated frustration from prior attempts. The reviewer then re-reviews. This loop repeats up to 5 rounds per step before the circuit breaker triggers.

**Circuit breaker monitoring:**

The coordinator watches for stuck loops:

| Signal | Threshold | What happens |
|--------|-----------|--------------|
| No file changes | 3 developer dispatches | Coordinator warns the next developer to try a different approach |
| Same error repeated | 5 times | Circuit breaker triggers (see replanning below) |
| Review rounds exceeded | 5 rounds | Circuit breaker triggers (see replanning below) |

**Replanning escalation (autonomous mode only):**

When the circuit breaker triggers due to persistent test failures, the coordinator can dispatch a **replanning agent** before halting. The replanning agent:

1. Analyzes why the tests can't be passed — is the implementation wrong, or are the tests wrong?
2. If the tests are correct: suggests a different implementation approach for the developer to try
3. If the tests are genuinely wrong: proposes specific test corrections with justification, applies them, creates a new TDD baseline tag (`tdd-baseline-<epic-name>-v2`), and logs the change prominently

This is a controlled release valve — it preserves test immutability as the default while giving autonomous mode a way forward when the plan was genuinely wrong. Only one replanning escalation is allowed per step; if it doesn't resolve the issue, the pipeline halts for human intervention.

In interactive mode, the circuit breaker always escalates to you directly — no automatic replanning.

**Step-level state tracking:**

Progress is tracked per step in `.execution-state.yaml`, so a resumed session picks up at the exact step that was interrupted — not from the beginning of the epic.

**What happens in the background:**
- Solution docs are written automatically when a developer resolves tricky problems. These accumulate in `kyros-agent-workflow/docs/solutions/` as your project's knowledge base.
- The reviewer validates that any new solution docs have correct YAML frontmatter.
````

**Step 3: Commit**

```bash
git add docs/user-guide.md
git commit -m "docs: update user guide Phase B for per-task agents and replanning"
```

---

### Task 6: Update user guide — Agents and Sub-Agents section

**Files:**
- Modify: `docs/user-guide.md:266-342` (Agents and Sub-Agents section)

**Step 1: Read the current file**

Read `docs/user-guide.md` lines 266-342 to confirm the agent lifecycle section.

**Step 2: Replace Phase B agent table and lifecycle diagram**

Replace the Phase B subsection (from `#### Phase B: Build` through the lifecycle summary closing ```) with:

````markdown
#### Phase B: Build

| Agent | Created by | Purpose | Torn down |
|-------|-----------|---------|-----------|
| **Build-step (coordinator)** | Orchestrator | Loops through steps, dispatches developer/reviewer per step, monitors circuit breakers, updates step-level state | After all steps pass review, or circuit breaker trips |
| **Developer** (per step) | Build-step coordinator | Implements code for one step, runs tests, self-reviews, commits | After completing that step's implementation |
| **Reviewer** (per step) | Build-step coordinator | Reviews one step's diff against review criteria, verifies tests pass, checks test immutability | After returning review verdict for that step |
| **Developer** (fix round) | Build-step coordinator | Fixes specific reviewer feedback for one step | After committing fixes |
| **Replanning agent** | Build-step coordinator (autonomous mode only) | Analyzes persistent test failures, proposes test corrections or alternative approaches | After returning verdict |

Each step gets a fresh developer and reviewer — they do not carry context from previous steps. If the reviewer requests changes, a new developer agent is spawned with the feedback. The replanning agent is only dispatched when the circuit breaker trips in autonomous mode.

#### Phase C: Submit

| Agent | Created by | Purpose | Torn down |
|-------|-----------|---------|-----------|
| **Submit-epic** | Orchestrator | Runs Definition of Done, quality scan, promotes learnings, creates PR (and auto-merges in autonomous mode) | After reporting PR created/merged |

If submit-epic reports a code-level DoD failure in autonomous mode, the orchestrator re-dispatches a **build-step** agent to fix the issue, then re-dispatches **submit-epic**. This retry loop runs up to 2 times before halting. Each re-dispatched agent is a fresh instance with no memory of prior attempts — the failure context is passed explicitly by the orchestrator.

#### Lifecycle summary

```
/execute-plan <epics-dir>
│
├─ Epic 1
│  ├─ Plan-epic ──────────────── created ──── torn down
│  │  └─ Learnings-researcher ─── created ─ torn down
│  │
│  ├─ Build-step (coordinator) ── created ──────────────────────────── torn down
│  │  ├─ Step 1: Developer ────── created ── torn down
│  │  │          Reviewer ─────── created ── torn down
│  │  ├─ Step 2: Developer ────── created ── torn down
│  │  │          Reviewer ─────── created ── torn down  (changes requested)
│  │  │          Developer ────── created ── torn down  (fix round)
│  │  │          Reviewer ─────── created ── torn down  (approved)
│  │  ├─ Step 3: Developer ────── created ── torn down
│  │  │          Reviewer ─────── created ── torn down
│  │  ...
│  │
│  └─ Submit-epic ────────────── created ──── torn down
│
├─ Epic 2 (fresh instances of everything)
│  ...
│
Orchestrator ───────────────────── lives for entire execution ─────────
```

No agent carries context between steps or between epics. Each developer and reviewer starts fresh. All continuity flows through files: the implementation plan, committed code, execution state YAML, solution docs, and progress logs.
````

**Step 3: Commit**

```bash
git add docs/user-guide.md
git commit -m "docs: update agent lifecycle section for per-task agents"
```

---

### Task 7: Update .harnessrc template and user guide config section

**Files:**
- Modify: `templates/.harnessrc.template:17-19` (agent team config)
- Modify: `docs/user-guide.md:360-368` (agent team config section)

**Step 1: Read the current files**

Read `templates/.harnessrc.template` and the config section of `docs/user-guide.md`.

**Step 2: Update .harnessrc template**

The `agent_team` config section should reflect that developer and reviewer are now per-task agents, not long-lived teammates. Replace lines 17-19:

```yaml
# Agent configuration
# agent:
#   developer_model: "sonnet"
#   reviewer_model: "sonnet"
#   replanning_model: "sonnet"
```

**Step 3: Update user guide config section**

Replace the "Agent team configuration" section in `docs/user-guide.md` (around lines 360-368) with:

```markdown
### Agent configuration

Choose which models the developer, reviewer, and replanning agents use:

```yaml
agent:
  developer_model: "sonnet"
  reviewer_model: "sonnet"
  replanning_model: "sonnet"
```
```

**Step 4: Commit**

```bash
git add templates/.harnessrc.template docs/user-guide.md
git commit -m "docs: update agent config for per-task agents and replanning model"
```

---

### Task 8: Update user guide Quick Reference and Troubleshooting

**Files:**
- Modify: `docs/user-guide.md:30` (Quick Reference — remove "conduct analyst Q&A" from profile-data description)
- Modify: `docs/user-guide.md:488-506` (Troubleshooting)

**Step 1: Read the relevant sections**

Read the Quick Reference table and Troubleshooting section.

**Step 2: Fix Quick Reference**

Line 30 says `/profile-data [paths]` description is "Profile data tables and conduct analyst Q&A". The analyst Q&A was removed in a prior PR. Update to:

```
| `/profile-data [paths]` | Profile data tables |
```

**Step 3: Add troubleshooting entry for replanning**

Add after the "Reviewer keeps requesting changes" entry:

```markdown
**Replanning triggered (autonomous mode)**
The replanning agent was dispatched because the circuit breaker tripped on persistent test failures. Check `<epics-dir>/claude-progress.txt` for the `REPLAN:` log entry, which includes the justification for any test changes. A new TDD baseline tag (`tdd-baseline-<epic-name>-v2`) was created. If you disagree with the test changes, revert the commit and re-run the build interactively.

**Build resumed at wrong step**
If the build seems to be re-doing completed work, check `.execution-state.yaml` for the step-level status. Steps marked `completed` will be skipped. If step state is missing or corrupt, delete the `steps:` block for that epic and re-run — the coordinator will re-initialize steps from the plan.
```

**Step 4: Commit**

```bash
git add docs/user-guide.md
git commit -m "docs: fix Quick Reference description and add troubleshooting entries"
```

---

### Task 9: Final integration verification

**Step 1: Run all BATS tests**

Run: `bats tests/`
Expected: All tests pass.

**Step 2: Verify file consistency**

Check that all cross-references are consistent:
- `build-step/SKILL.md` references functions that exist in `lib/state.sh`
- `execute-plan/SKILL.md` passes `mode` to build-step
- `harness-status/SKILL.md` references step-level state that `execution_summary` can produce
- User guide matches the skills
- `.harnessrc.template` config keys match what the skills reference

**Step 3: Create PR**

```bash
git checkout -b feat/per-task-agents-and-replanning
# (or use the branch created at the start)
git push -u origin feat/per-task-agents-and-replanning
```

Create PR with title: "Per-task agents, step-level state tracking, and replanning escalation"
