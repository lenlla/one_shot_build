# Command Restructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the `/next`-driven linear workflow with explicit commands (`/profile-data`, `/define-epics`, `/execute-plan`, `/execute-plan-autonomously`), remove global phase tracking, and scope execution state to epics directories.

**Architecture:** Refactor existing skills (Approach A). New command files are thin entry points that invoke refactored skills. A new `execute-plan` orchestrator skill manages the epic loop, dispatching sub-agents for plan/build/submit phases. State tracking moves from global `project-state.yaml` to per-directory `.execution-state.yaml`.

**Tech Stack:** Bash (hooks, state lib), Markdown (skills, commands), JavaScript (dashboard), BATS (tests), yq (YAML manipulation)

**Design doc:** `docs/plans/2026-02-18-command-restructure-design.md`

---

## Phase 1: State Library Foundation

### Task 1: Refactor `lib/state.sh` to support execution state

**Files:**
- Modify: `lib/state.sh`

The state library currently hardcodes paths to `project-state.yaml`. Refactor to support both the legacy state file (for backward compat during migration) and the new `.execution-state.yaml` scoped to an epics directory.

**Step 1: Add execution state path helpers**

Add these functions after the existing convenience functions in `lib/state.sh`:

```bash
# --- Execution state operations ---

# Resolve the path to .execution-state.yaml for a given epics directory
# Usage: execution_state_file "/path/to/epics/v1"
execution_state_file() {
    local epics_dir="$1"
    echo "${epics_dir}/.execution-state.yaml"
}

# Read a value from an execution state file
# Usage: read_execution_state "/path/to/epics/v1" "epics.data-loading.status"
read_execution_state() {
    local epics_dir="$1"
    local path="$2"
    local state_file
    state_file=$(execution_state_file "$epics_dir")

    if [[ ! -f "$state_file" ]]; then
        echo ""
        return 0
    fi

    local yq_path=".${path}"
    if command -v yq &>/dev/null; then
        local result
        result=$(yq eval "$yq_path" "$state_file" 2>/dev/null || echo "")
        if [[ "$result" == "null" ]]; then
            echo ""
        else
            echo "$result"
        fi
    else
        echo "Error: yq is required for execution state reads." >&2
        return 1
    fi
}

# Update a value in an execution state file
# Usage: update_execution_state "/path/to/epics/v1" "epics.data-loading.status" "completed"
update_execution_state() {
    local epics_dir="$1"
    local path="$2"
    local value="$3"
    local state_file
    state_file=$(execution_state_file "$epics_dir")

    if [[ ! -f "$state_file" ]]; then
        echo "Error: Execution state file not found at $state_file" >&2
        return 1
    fi

    local yq_path=".${path}"
    if command -v yq &>/dev/null; then
        yq eval -i "${yq_path} = \"${value}\"" "$state_file"
    else
        echo "Error: yq is required for execution state updates." >&2
        return 1
    fi
}

# Find all .execution-state.yaml files in the project
# Usage: find_execution_states
find_execution_states() {
    find "$PROJECT_ROOT" -name ".execution-state.yaml" -not -path "*/.git/*" 2>/dev/null || true
}

# Find active (non-completed) execution states
# Usage: find_active_executions
find_active_executions() {
    local states
    states=$(find_execution_states)

    if [[ -z "$states" ]]; then
        return 0
    fi

    while IFS= read -r state_file; do
        local epics_dir
        epics_dir=$(dirname "$state_file")
        # Check if any epic is not completed
        local pending
        pending=$(yq eval '.epics | to_entries | .[] | select(.value.status != "completed") | .key' "$state_file" 2>/dev/null || echo "")
        if [[ -n "$pending" ]]; then
            echo "$epics_dir"
        fi
    done <<< "$states"
}

# Get a human-readable summary of an execution state
# Usage: execution_summary "/path/to/epics/v1"
execution_summary() {
    local epics_dir="$1"
    local state_file
    state_file=$(execution_state_file "$epics_dir")

    if [[ ! -f "$state_file" ]]; then
        echo "No execution state found"
        return 0
    fi

    local total completed current_epic current_status current_step
    total=$(yq eval '.epics | length' "$state_file" 2>/dev/null || echo "0")
    completed=$(yq eval '.epics | to_entries | .[] | select(.value.status == "completed") | .key' "$state_file" 2>/dev/null | wc -l | tr -d ' ')
    current_epic=$(yq eval '.epics | to_entries | .[] | select(.value.status != "completed" and .value.status != "pending") | .key' "$state_file" 2>/dev/null | head -1)

    if [[ -n "$current_epic" ]]; then
        current_status=$(yq eval ".epics.\"${current_epic}\".status" "$state_file" 2>/dev/null || echo "")
        current_step=$(yq eval ".epics.\"${current_epic}\".current_step" "$state_file" 2>/dev/null || echo "")
        local steps_total
        steps_total=$(yq eval ".epics.\"${current_epic}\".steps_total" "$state_file" 2>/dev/null || echo "")
        if [[ -n "$current_step" && -n "$steps_total" && "$steps_total" != "null" ]]; then
            echo "${completed}/${total} epics done, currently on '${current_epic}' step ${current_step}/${steps_total}"
        else
            echo "${completed}/${total} epics done, currently on '${current_epic}' (${current_status})"
        fi
    else
        echo "${completed}/${total} epics done"
    fi
}
```

**Step 2: Run existing tests to verify no regression**

Run: `npx bats tests/state_test.bats`
Expected: All existing tests PASS (new functions don't break old ones)

**Step 3: Commit**

```bash
git add lib/state.sh
git commit -m "feat(state): add execution state helpers for directory-scoped state"
```

---

### Task 2: Add tests for execution state functions

**Files:**
- Modify: `tests/state_test.bats`

**Step 1: Write tests for the new execution state functions**

Append these tests to the end of `tests/state_test.bats`:

```bash
# --- execution state tests ---

@test "execution_state_file returns correct path" {
    run execution_state_file "/tmp/epics/v1"
    assert_success
    assert_output "/tmp/epics/v1/.execution-state.yaml"
}

@test "read_execution_state returns empty when no file exists" {
    run read_execution_state "/tmp/nonexistent" "epics.test.status"
    assert_success
    assert_output ""
}

@test "read_execution_state reads epic status" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
started_at: "2026-02-18T14:30:00Z"
mode: interactive
epics:
  data-loading:
    status: completed
  transformation:
    status: building
    current_step: 3
    steps_total: 5
YAML
    run read_execution_state "$TEST_DIR/epics/v1" "epics.data-loading.status"
    assert_success
    assert_output "completed"
}

@test "update_execution_state writes epic status" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: pending
YAML
    run update_execution_state "$TEST_DIR/epics/v1" "epics.data-loading.status" "building"
    assert_success

    run read_execution_state "$TEST_DIR/epics/v1" "epics.data-loading.status"
    assert_output "building"
}

@test "find_execution_states finds state files in project" {
    mkdir -p "$TEST_DIR/epics/v1" "$TEST_DIR/epics/v2"
    echo "epics: {}" > "$TEST_DIR/epics/v1/.execution-state.yaml"
    echo "epics: {}" > "$TEST_DIR/epics/v2/.execution-state.yaml"

    run find_execution_states
    assert_success
    assert_output --partial "epics/v1/.execution-state.yaml"
    assert_output --partial "epics/v2/.execution-state.yaml"
}

@test "find_active_executions only returns dirs with incomplete epics" {
    mkdir -p "$TEST_DIR/epics/v1" "$TEST_DIR/epics/v2"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: completed
YAML
    cat > "$TEST_DIR/epics/v2/.execution-state.yaml" <<'YAML'
epics:
  transform:
    status: building
YAML

    run find_active_executions
    assert_success
    assert_output --partial "epics/v2"
    refute_output --partial "epics/v1"
}

@test "execution_summary shows progress" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: completed
  transformation:
    status: building
    current_step: 3
    steps_total: 5
  reporting:
    status: pending
YAML

    run execution_summary "$TEST_DIR/epics/v1"
    assert_success
    assert_output --partial "1/3 epics done"
    assert_output --partial "transformation"
}
```

**Step 2: Run the new tests to verify they pass**

Run: `npx bats tests/state_test.bats`
Expected: All tests PASS (both old and new)

**Step 3: Commit**

```bash
git add tests/state_test.bats
git commit -m "test(state): add tests for execution state helpers"
```

---

## Phase 2: New Command Entry Points

### Task 3: Create all new command files

**Files:**
- Create: `commands/profile-data.md`
- Create: `commands/define-epics.md`
- Create: `commands/execute-plan.md`
- Create: `commands/execute-plan-autonomously.md`

**Step 1: Create `commands/profile-data.md`**

```markdown
---
description: "Profile client data tables. Creates a data-profile markdown file for each table."
disable-model-invocation: true
---

Invoke the one-shot-build:gather-context skill and follow it exactly as presented to you.

Arguments passed by the user (if any) are table paths to profile. If no arguments were provided, the skill will ask for them.

User arguments: $ARGUMENTS
```

**Step 2: Create `commands/define-epics.md`**

```markdown
---
description: "Brainstorm and define project epics collaboratively with the analyst."
disable-model-invocation: true
---

Invoke the one-shot-build:define-epics skill and follow it exactly as presented to you.

Arguments passed by the user (if any) are paths to context files (data profiles, docs, requirements). If no arguments were provided, the skill will ask for them.

User arguments: $ARGUMENTS
```

**Step 3: Create `commands/execute-plan.md`**

```markdown
---
description: "Execute an epic plan interactively — plan, build, and submit each epic with human checkpoints."
disable-model-invocation: true
---

Invoke the one-shot-build:execute-plan skill and follow it exactly as presented to you.

Pass these parameters to the skill:
- **mode:** interactive
- **epics_dir:** The first argument from the user (if provided). If not provided, the skill will ask for it.

User arguments: $ARGUMENTS
```

**Step 4: Create `commands/execute-plan-autonomously.md`**

```markdown
---
description: "Execute an epic plan autonomously — plan, build, and submit each epic with minimal human intervention."
disable-model-invocation: true
---

Invoke the one-shot-build:execute-plan skill and follow it exactly as presented to you.

Pass these parameters to the skill:
- **mode:** autonomous
- **epics_dir:** The first argument from the user (if provided). If not provided, the skill will ask for it.

User arguments: $ARGUMENTS
```

**Step 5: Commit**

```bash
git add commands/profile-data.md commands/define-epics.md commands/execute-plan.md commands/execute-plan-autonomously.md
git commit -m "feat(commands): add profile-data, define-epics, execute-plan, execute-plan-autonomously"
```

---

## Phase 3: Skill Refactoring

### Task 4: Refactor `gather-context` skill for `/profile-data`

**Files:**
- Modify: `skills/gather-context/SKILL.md`

Replace the entire content of `skills/gather-context/SKILL.md` with the following. This strips the analyst Q&A, adds multi-table support, per-table output naming, and existing profile detection.

**Step 1: Rewrite the skill**

```markdown
---
name: gather-context
description: Profile client data tables. Creates one data-profile-<table>.md per table. Supports multiple tables. Detects existing profiles and asks whether to overwrite or create a new version.
---

# Profile Data

## Overview

Run automated data profiling on one or more client data tables. Each table gets its own profile report.

## Pre-Conditions

- Project has been initialized with `/init`
- Client data tables are accessible

## Process

### Step 1: Determine tables to profile

Check if the user provided table paths as arguments to the `/profile-data` command.

- **If arguments provided:** Use those as the table paths.
- **If no arguments:** Use AskUserQuestion to ask: "What tables should I profile? Provide the path(s) to your data tables (CSV, Excel, Parquet, or database table references). You can specify multiple tables separated by spaces."

### Step 2: Check for existing profiles

For each table, check if a profile already exists at `kyros-agent-workflow/docs/context/data-profile-<table-name>.md`.

If a profile exists for any table, use AskUserQuestion to ask for each one:
"A profile already exists for `<table-name>`. Would you like to:"
- Overwrite the existing profile
- Create a new version (saves as `data-profile-<table-name>-v<N>.md`)

### Step 3: Profile each table

For each table, dispatch the **profiler** subagent with the Task tool:
- subagent_type: use the `profiler` agent definition
- Prompt: "Profile the data at [path]. Write results to kyros-agent-workflow/docs/context/data-profile-<table-name>.md."
  - Include column types, distributions, null counts, unique values, min/max, data quality issues
  - If this is a versioned profile, use the versioned filename
- Wait for the profiler to complete before starting the next table

### Step 4: Present summaries

For each profiled table, read the generated profile and present a brief summary to the analyst:
- Number of rows and columns
- Key data quality concerns (high nulls, low variance, type mismatches)
- Notable patterns

### Step 5: Commit

```bash
git add kyros-agent-workflow/docs/context/data-profile-*.md
git commit -m "docs: add data profiles for <table-names>"
```

Tell the user: "Data profiling complete. You can now run `/define-epics` to plan your project, passing these profiles as context if desired."
```

**Step 2: Commit**

```bash
git add skills/gather-context/SKILL.md
git commit -m "refactor(gather-context): strip Q&A, add multi-table profiling, existing profile detection"
```

---

### Task 5: Refactor `define-epics` skill with brainstorming flow

**Files:**
- Modify: `skills/define-epics/SKILL.md`

Replace the entire content with the brainstorming-driven flow.

**Step 1: Rewrite the skill**

```markdown
---
name: define-epics
description: Brainstorm what to build, gather context, and collaboratively define project epics. Opens with "What do you want to build today?" If data profiles are provided as context, asks targeted data questions. Saves epic YAML specs to an analyst-named directory.
---

# Define Epics

## Overview

A collaborative brainstorming and planning session. Explore what the analyst wants to build, understand the context, then break the work into sequential epics.

## Process

### Step 1: Open the brainstorming

Start with: **"What do you want to build today?"**

Let the analyst describe their vision. Listen and ask follow-up questions ONE at a time. Prefer multiple-choice questions when possible.

### Step 2: Gather context

Check if the user provided context file paths as arguments to the `/define-epics` command.

- **If arguments provided:** Read each file. Acknowledge what you've learned from each.
- **If no arguments:** Use AskUserQuestion: "Can you point me to any relevant context? This could include data profiles, requirements docs, existing code, or configuration files. Provide file paths or say 'none' to continue."

Read all provided context files.

### Step 3: Data-specific questions (if data profile provided)

If any of the context files is a data profile (`data-profile-*.md`), ask targeted questions about the data. ONE question at a time:

- "I see [N] columns in [table]. Are there columns that should be excluded from analysis?"
- "The [column] has [X]% null values. Is this expected? How should nulls be handled?"
- "I notice [pattern]. Is this a known characteristic of this data?"
- "What is the target variable for modeling?"
- "Are there any domain-specific constraints I should know about?"

Only ask questions that are relevant based on what the profile reveals. Skip questions where the answer is obvious from the data.

### Step 4: Search knowledge base (optional)

If a shared knowledge repo is configured in `.harnessrc` (`shared_knowledge_path`), ask the analyst:
"Would you like me to search past projects for similar work that could inform our epic breakdown?"

If yes, dispatch the **learnings-researcher** subagent with project context. Use findings to inform the epic proposal.

### Step 5: Propose epic breakdown

Based on everything gathered, propose a breakdown of the project into sequential epics:

```
## Proposed Epics

1. **[Epic Name]** — [One-line description]
   - Acceptance criteria: [2-3 bullet points]
2. **[Epic Name]** — [One-line description]
   - Acceptance criteria: [2-3 bullet points]
...
```

Lead with your recommended breakdown and explain the reasoning.

### Step 6: Refine with analyst

Ask ONE question at a time to refine:
- "Does this epic breakdown match how you see the project?"
- "Should any epics be split or combined?"
- "What's the right order?"
- "Are there epics I'm missing?"

Iterate until the analyst approves the breakdown.

### Step 7: Name the output directory

Use AskUserQuestion: "What should I name the epics directory? This is where the epic specs will be saved and where `/execute-plan` will look for them. Examples: `epics/v1`, `epics/initial-model`, `epics/feature-x`"

Create the directory.

### Step 8: Write epic specs

For each agreed epic, create a YAML file in the named directory:

```yaml
# <epics-dir>/01-<epic-name>.yaml
name: "[Epic Name]"
description: "[Detailed description]"
acceptance_criteria:
  - "[Criterion 1]"
  - "[Criterion 2]"
  - "[Criterion 3]"
dependencies: []
estimated_steps: 4
```

Number the files to preserve ordering (01-, 02-, etc.).

### Step 9: Commit

```bash
git add <epics-dir>/
git commit -m "docs: define epics in <epics-dir>"
```

Tell the user: "Epics defined in `<epics-dir>/`. When you're ready to start building, run `/execute-plan <epics-dir>` (interactive) or `/execute-plan-autonomously <epics-dir>` (fully autonomous)."
```

**Step 2: Commit**

```bash
git add skills/define-epics/SKILL.md
git commit -m "refactor(define-epics): add brainstorming flow, context gathering, directory naming"
```

---

### Task 6: Refactor `plan-epic` skill to accept parameters

**Files:**
- Modify: `skills/plan-epic/SKILL.md`

Remove global state dependency. The skill now receives the epic spec path and epics directory as context from the orchestrator.

**Step 1: Rewrite the skill**

```markdown
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
```

**Step 2: Commit**

```bash
git add skills/plan-epic/SKILL.md
git commit -m "refactor(plan-epic): accept parameters from orchestrator, remove global state dependency"
```

---

### Task 7: Refactor `build-step` skill to accept parameters

**Files:**
- Modify: `skills/build-step/SKILL.md`

Remove global state dependency. The skill now receives context from the orchestrator and writes circuit breaker state to `.execution-state.yaml`.

**Step 1: Rewrite the skill**

```markdown
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
```

**Step 2: Commit**

```bash
git add skills/build-step/SKILL.md
git commit -m "refactor(build-step): accept parameters from orchestrator, remove global state dependency"
```

---

### Task 8: Refactor `submit-epic` skill to accept parameters

**Files:**
- Modify: `skills/submit-epic/SKILL.md`

Remove global state dependency. Mode (interactive/autonomous) is passed as a parameter. State reads/writes go to `.execution-state.yaml`.

**Step 1: Rewrite the skill**

```markdown
---
name: submit-epic
description: Run Definition of Done checks, quality scan, and create a PR for a completed epic. Called by the execute-plan orchestrator — receives epic context and execution mode as parameters.
---

# Submit Epic

## Overview

Run final quality checks and submit a PR for a completed epic.

## Context (provided by orchestrator)

This skill is invoked by the `execute-plan` orchestrator as a sub-agent. The orchestrator provides:
- **epic_name**: Name identifier for this epic
- **epics_dir**: Path to the epics directory
- **mode**: `interactive` or `autonomous`
- **tdd_baseline_tag**: Git tag for immutability checks

## Process

### Step 1: Run Definition of Done

Execute the DoD checklist:
```bash
bash <plugin_root>/hooks/definition-of-done.sh <epics_dir>
```

**If it fails:**
- **Interactive mode:** Report failures back to orchestrator for human review.
- **Autonomous mode:** Attempt to fix each failure automatically:
  - TODO comments: remove or replace with implementation
  - Debug prints: remove
  - Empty progress file: write epic summary
  - After fixing, re-run DoD. If still failing after 3 attempts, halt and report to orchestrator.

### Step 2: Run quality scan

```bash
bash <plugin_root>/hooks/quality-scan.sh
```

**If findings reported:**
- **Interactive mode:** Include findings in the report to the orchestrator. Non-blocking.
- **Autonomous mode:** Auto-fix what can be fixed (unused imports, formatting). Include remaining issues in PR description. Commit fixes before proceeding.

### Step 3: Promote cross-project learnings

Review `kyros-agent-workflow/docs/solutions/` for solution docs created during this epic.

For each doc where `applies_to.scope` is `universal`:
- **Interactive mode:** Include in report for orchestrator to present to user.
- **Autonomous mode:** If `shared_knowledge_path` is configured, automatically promote. Log to progress file.

### Step 4: Commit final state

```bash
git add kyros-agent-workflow/claude-progress.txt
git commit -m "chore: finalize epic <name> for submission"
```

### Step 5: Create the PR

```bash
git push origin epic/<epic-name>
gh pr create --base main --head epic/<epic-name> --title "Epic: <epic-name>" --body "<summary>"
```

Capture the PR number from the output.

### Step 6: Auto-merge (autonomous mode only)

**Interactive mode:** Skip. Report PR URL to orchestrator.

**Autonomous mode:**
```bash
gh pr merge <number> --merge --delete-branch
git checkout main && git pull origin main
```

If merge fails, halt and report to orchestrator.

### Step 7: Report to orchestrator

Report back with:
- PR number and URL
- DoD result (pass/fail details)
- Quality scan findings (if any)
- Learnings to promote (if interactive mode)
- Merge status (if autonomous mode)
```

**Step 2: Commit**

```bash
git add skills/submit-epic/SKILL.md
git commit -m "refactor(submit-epic): accept parameters from orchestrator, mode as parameter"
```

---

### Task 9: Create the `execute-plan` orchestrator skill

**Files:**
- Create: `skills/execute-plan/SKILL.md`

This is the core new skill — the orchestrator that runs the plan/build/submit loop.

**Step 1: Create the skill directory and file**

```bash
mkdir -p skills/execute-plan
```

Write `skills/execute-plan/SKILL.md`:

```markdown
---
name: execute-plan
description: Orchestrate execution of an epic plan. Loops through each epic in the specified directory, dispatching sub-agents for planning, building, and submitting. Supports interactive and autonomous modes.
---

# Execute Plan

## Overview

The orchestrator for epic execution. Manages the plan -> build -> submit loop for each epic, dispatching sub-agents for all heavy work. The orchestrator stays lean — it only coordinates, updates state, and handles user interaction.

## Parameters

This skill receives from the command entry point:
- **mode**: `interactive` or `autonomous` (from which command was used)
- **epics_dir**: Path to the epics directory (from user argument, or ask if not provided)

## Startup Sequence

### Step 1: Resolve epics directory

If `epics_dir` was provided as an argument, use it. Otherwise, use AskUserQuestion:
"Which epics directory should I execute? Provide the path (e.g., `epics/v1`)."

Verify the directory exists and contains `.yaml` epic spec files. If not, report the error and stop.

### Step 2: Check for concurrent executions

Source `<plugin_root>/lib/state.sh` and call `find_active_executions`.

If other active execution states are found, warn the user:
"There are other active executions in progress:
- `<other-dir>` — <summary>

Running concurrent executions against the same codebase can cause branch and merge conflicts. Do you want to proceed anyway?"

Use AskUserQuestion with options: "Yes, proceed" / "No, cancel"

### Step 3: Check context usage

Check the current context window usage. If it appears high (the session has significant prior conversation), recommend clearing:

"Your context window has significant prior usage. For best results during execution, I recommend starting fresh. You can:
1. Run `/clear` to clear conversation history in this session
2. Start a new Claude Code session and run the execute command there

Would you like to proceed anyway, or clear first?"

Use AskUserQuestion with options: "Proceed anyway" / "I'll clear and restart"

If "I'll clear and restart": remind them of the exact command to run after clearing, then stop.

### Step 4: Permission check (autonomous mode only)

**Only for `/execute-plan-autonomously`:**

Check if Claude Code is running with `--dangerously-skip-permissions`. This can be detected by attempting a tool call that would normally require permission — if it succeeds without prompting, the flag is active.

If the flag is NOT detected:
"Autonomous mode works best with `--dangerously-skip-permissions` to avoid permission prompts during unattended execution.

To restart with this flag:
```bash
claude --dangerously-skip-permissions
```

Then run: `/execute-plan-autonomously <epics-dir>`

Do you want to proceed without the flag? You'll need to approve permission prompts manually."

Use AskUserQuestion with options: "Proceed without flag" / "I'll restart with the flag"

### Step 5: Check for existing execution state

Check if `<epics_dir>/.execution-state.yaml` exists.

**If exists:** Read it and show a summary using `execution_summary`:
"Previous execution found: <summary>

Would you like to resume from where you left off, or start fresh?"

Use AskUserQuestion with options: "Resume" / "Start fresh"

If "Start fresh": delete the existing `.execution-state.yaml`.

**If not exists (or starting fresh):** Read all `.yaml` files in the epics directory (sorted by filename to preserve ordering). Create `.execution-state.yaml`:

```yaml
started_at: "<current ISO timestamp>"
mode: <interactive|autonomous>
epics:
  <epic-name-1>:
    status: pending
  <epic-name-2>:
    status: pending
  ...
```

## Main Loop

For each epic with status `pending` or any in-progress status (planning, building, submitting):

### Phase A: Plan Epic

Update state: set epic status to `planning`.

Dispatch a **sub-agent** with the Task tool:
- Prompt: Invoke the plan-epic skill with context:
  - epic_spec_path: `<epics_dir>/<epic-file>`
  - epics_dir: `<epics_dir>`
  - epic_name: `<epic-name>`
- Wait for completion

When sub-agent returns, update state: set epic status to `building`.

**Interactive mode pause:** "Planning complete for '<epic-name>'. Tests written and implementation plan created. Ready to start building?"
Use AskUserQuestion: "Proceed to build" / "Review the plan first" / "Stop here"

### Phase B: Build Epic

Update state: set epic status to `building`.

Dispatch a **sub-agent** with the Task tool:
- Prompt: Invoke the build-step skill with context:
  - epic_name: `<epic-name>`
  - epics_dir: `<epics_dir>`
  - plan_path: `kyros-agent-workflow/docs/plans/<epic-name>-plan.md`
  - epic_spec_path: `<epics_dir>/<epic-file>`
  - tdd_baseline_tag: `tdd-baseline-<epic-name>`
- Wait for completion

Monitor the sub-agent's response for circuit breaker trips. If a halt is reported:
- Update state with failure context
- **Both modes:** Surface the issue to the user. "Build halted for '<epic-name>': <reason>. What would you like to do?"
- Stop the loop until the user intervenes

When sub-agent returns successfully, update state: set epic status to `submitting`.

### Phase C: Submit Epic

Update state: set epic status to `submitting`.

Dispatch a **sub-agent** with the Task tool:
- Prompt: Invoke the submit-epic skill with context:
  - epic_name: `<epic-name>`
  - epics_dir: `<epics_dir>`
  - mode: `<interactive|autonomous>`
  - tdd_baseline_tag: `tdd-baseline-<epic-name>`
- Wait for completion

When sub-agent returns, capture the PR number/URL from its report.

Update state: set epic status to `completed`, record PR reference, set completed_at timestamp.

**Interactive mode pause:** "PR created for '<epic-name>': <URL>. Please merge the PR when ready, then confirm to continue to the next epic."
Use AskUserQuestion: "PR merged, continue" / "Stop here"

**Autonomous mode:** Continue immediately to next epic (merge already done by submit sub-agent).

### Between Epics

After completing an epic and before starting the next:

**Interactive mode:** "Completed <N> of <total> epics. Next up: '<next-epic>'. Proceed?"
Use AskUserQuestion: "Proceed" / "Stop here"

**Autonomous mode:** Continue immediately.

## Completion

When all epics are completed:

Update state: record overall completion timestamp.

**Interactive mode:** "All <N> epics complete! Here's a summary:
- <epic-1>: PR #<n>
- <epic-2>: PR #<n>
- ...

Project execution is done."

**Autonomous mode:** Log completion to `kyros-agent-workflow/claude-progress.txt`. "All epics complete. Execution finished."

## Error Handling

- **Circuit breaker trip:** Halt and surface to user regardless of mode
- **Merge conflict:** Halt and notify
- **Sub-agent failure:** Log context, halt, surface to user
- **Permission denial in autonomous mode:** Warn about --dangerously-skip-permissions flag
```

**Step 2: Commit**

```bash
git add skills/execute-plan/SKILL.md
git commit -m "feat(execute-plan): create orchestrator skill for epic execution loop"
```

---

## Phase 4: Hooks Refactoring

### Task 10: Refactor `session-start.sh` for execution state

**Files:**
- Modify: `hooks/session-start.sh`

Replace global phase tracking with execution state scanning.

**Step 1: Rewrite the hook**

Replace the entire content of `hooks/session-start.sh`:

```bash
#!/usr/bin/env bash
# hooks/session-start.sh — Scans for active execution states and injects workflow context
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source state library
source "${PLUGIN_ROOT}/lib/state.sh"

# Escape string for JSON embedding
escape_for_json() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

# Build context message
context=""

# Check for active execution states
active_dirs=$(find_active_executions)

if [[ -n "$active_dirs" ]]; then
    # Count active executions
    active_count=$(echo "$active_dirs" | wc -l | tr -d ' ')

    if [[ "$active_count" -eq 1 ]]; then
        dir=$(echo "$active_dirs" | head -1)
        summary=$(execution_summary "$dir")
        context="## One-Shot Build Harness Active\\n\\n"
        context+="**Active execution:** \`${dir}\` — ${summary}\\n\\n"
        context+="Run \`/execute-plan ${dir}\` to resume."
    else
        context="## One-Shot Build Harness Active\\n\\n"
        context+="**Active executions:**\\n\\n"
        while IFS= read -r dir; do
            summary=$(execution_summary "$dir")
            context+="  - \`${dir}\` — ${summary}\\n"
        done <<< "$active_dirs"
        context+="\\nRun \`/execute-plan <dir>\` to resume one."
    fi

    context+="\\n\\nOther commands: \`/profile-data\`, \`/define-epics\`, \`/status\`, \`/board\`"
else
    context="## One-Shot Build Harness\\n\\n"
    context+="No active executions found.\\n\\n"
    context+="**Available commands:**\\n"
    context+="- \`/init\` — Scaffold a new project\\n"
    context+="- \`/profile-data\` — Profile data tables\\n"
    context+="- \`/define-epics\` — Brainstorm and define project epics\\n"
    context+="- \`/execute-plan <dir>\` — Execute epics interactively\\n"
    context+="- \`/execute-plan-autonomously <dir>\` — Execute epics autonomously\\n"
    context+="- \`/status\` — Check workflow state\\n"
    context+="- \`/board\` — Open Kanban dashboard"
fi

escaped_context=$(escape_for_json "$context")

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "${escaped_context}"
  }
}
EOF

exit 0
```

**Step 2: Run existing session-start tests**

Run: `npx bats tests/session_start_test.bats`
Expected: Some tests will FAIL because they reference `project-state.yaml`. This is expected — we'll fix the tests in the next task.

**Step 3: Commit**

```bash
git add hooks/session-start.sh
git commit -m "refactor(session-start): scan for execution state files instead of global phase"
```

---

### Task 11: Refactor `definition-of-done.sh` to accept epics directory

**Files:**
- Modify: `hooks/definition-of-done.sh`

The hook now accepts the epics directory as an argument and reads epic/step state from `.execution-state.yaml`.

**Step 1: Rewrite the hook**

Replace the entire content of `hooks/definition-of-done.sh`:

```bash
#!/usr/bin/env bash
# hooks/definition-of-done.sh
# Runs the Definition of Done checklist before PR submission.
# Usage: definition-of-done.sh <epics-dir> [epic-name]
# Exit 0 = PASS, Exit 1 = FAIL with details

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source state library
source "${PLUGIN_ROOT}/lib/state.sh"

EPICS_DIR="${1:?Usage: definition-of-done.sh <epics-dir> [epic-name]}"
EPIC="${2:-}"

# If epic not provided, try to detect from execution state
if [[ -z "$EPIC" ]]; then
    local_state=$(execution_state_file "$EPICS_DIR")
    if [[ -f "$local_state" ]] && command -v yq &>/dev/null; then
        EPIC=$(yq eval '.epics | to_entries | .[] | select(.value.status == "submitting" or .value.status == "building") | .key' "$local_state" 2>/dev/null | head -1)
    fi
fi

if [[ -z "$EPIC" ]]; then
    echo "FAIL: Could not determine current epic. Provide epic name as second argument."
    exit 1
fi

failures=()

# --- Check 1: No TODO comments in src/ ---
if [[ -d "${HARNESS_DIR}/src" ]]; then
    todos=$(grep -rn "TODO\|FIXME\|HACK\|XXX" "${HARNESS_DIR}/src/" 2>/dev/null || true)
    if [[ -n "$todos" ]]; then
        failures+=("TODO/FIXME comments found in ${HARNESS_DIR}/src/:\n$todos")
    fi
fi

# --- Check 2: No debug print statements ---
if [[ -d "${HARNESS_DIR}/src" ]]; then
    debug_prints=$(grep -rn "print(" "${HARNESS_DIR}/src/" --include="*.py" 2>/dev/null | grep -v "# noqa" || true)
    if [[ -n "$debug_prints" ]]; then
        failures+=("Debug print() statements found in ${HARNESS_DIR}/src/:\n$debug_prints")
    fi
fi

# --- Check 3: claude-progress.txt exists and is non-empty ---
if [[ ! -s "$PROGRESS_FILE" ]]; then
    failures+=("claude-progress.txt is empty or missing")
fi

# --- Check 4: No uncommitted changes ---
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    failures+=("Uncommitted changes detected. Commit all work before submitting.")
fi

# --- Report ---
if [[ ${#failures[@]} -eq 0 ]]; then
    echo "PASS: All Definition of Done criteria met for epic ${EPIC}"
    exit 0
else
    echo "FAIL: Definition of Done check failed for epic ${EPIC}"
    echo ""
    for fail in "${failures[@]}"; do
        echo -e "  - $fail"
    done
    echo ""
    echo "Fix these issues before submitting."
    exit 1
fi
```

**Step 2: Commit**

```bash
git add hooks/definition-of-done.sh
git commit -m "refactor(definition-of-done): accept epics dir argument, remove global state dependency"
```

---

### Task 12: Update `self-check.sh` to pass epics dir

**Files:**
- Modify: `hooks/self-check.sh`

Minor update — the hook's interface stays the same but it passes context correctly to sub-hooks.

**Step 1: Update self-check.sh**

The current `self-check.sh` already accepts `step-name`, `epic-name`, and `tdd-baseline-ref`. No changes needed to its interface since it doesn't read global state directly — it delegates to `check-test-immutability.sh` (which already accepts a baseline ref) and `validate-solution-doc.sh` (which is stateless).

Verify by reading the file — the only concern is the `pytest` call and the sub-hook calls. These are already parameterized. **No changes needed.**

**Step 2: Commit (skip if no changes)**

No commit needed — `self-check.sh` already works with the new model.

---

### Task 13: Update BATS tests for new state model

**Files:**
- Modify: `tests/session_start_test.bats`
- Modify: `tests/definition_of_done_test.bats`

**Step 1: Rewrite `tests/session_start_test.bats`**

```bash
#!/usr/bin/env bats
# tests/session_start_test.bats

setup() {
    load "${BATS_TEST_DIRNAME}/../node_modules/bats-support/load"
    load "${BATS_TEST_DIRNAME}/../node_modules/bats-assert/load"

    TEST_DIR="$(mktemp -d)"
    export PROJECT_ROOT="$TEST_DIR"

    # Create the harness directory structure
    mkdir -p "$TEST_DIR/kyros-agent-workflow"

    SCRIPT_DIR="${BATS_TEST_DIRNAME}/../hooks"
}

teardown() {
    rm -rf "$TEST_DIR"
}

@test "session-start outputs valid JSON" {
    cd "$TEST_DIR"
    run bash "${SCRIPT_DIR}/session-start.sh"
    assert_success
    assert_output --partial "hookSpecificOutput"
}

@test "session-start shows active execution when state exists" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
started_at: "2026-02-18T14:30:00Z"
mode: interactive
epics:
  data-loading:
    status: building
    current_step: 2
    steps_total: 4
YAML

    cd "$TEST_DIR"
    run bash "${SCRIPT_DIR}/session-start.sh"
    assert_success
    assert_output --partial "Active execution"
    assert_output --partial "epics/v1"
}

@test "session-start handles no execution states gracefully" {
    cd "$TEST_DIR"
    run bash "${SCRIPT_DIR}/session-start.sh"
    assert_success
    assert_output --partial "hookSpecificOutput"
    assert_output --partial "No active executions"
}

@test "session-start lists multiple active executions" {
    mkdir -p "$TEST_DIR/epics/v1" "$TEST_DIR/epics/v2"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
YAML
    cat > "$TEST_DIR/epics/v2/.execution-state.yaml" <<'YAML'
epics:
  transform:
    status: planning
YAML

    cd "$TEST_DIR"
    run bash "${SCRIPT_DIR}/session-start.sh"
    assert_success
    assert_output --partial "Active executions"
    assert_output --partial "epics/v1"
    assert_output --partial "epics/v2"
}
```

**Step 2: Rewrite `tests/definition_of_done_test.bats`**

```bash
#!/usr/bin/env bats
# tests/definition_of_done_test.bats

setup() {
    load "${BATS_TEST_DIRNAME}/../node_modules/bats-support/load"
    load "${BATS_TEST_DIRNAME}/../node_modules/bats-assert/load"

    TEST_DIR="$(mktemp -d)"
    export PROJECT_ROOT="$TEST_DIR"

    SCRIPT="${BATS_TEST_DIRNAME}/../hooks/definition-of-done.sh"

    # Create minimal project structure
    mkdir -p "$TEST_DIR/kyros-agent-workflow/tests" "$TEST_DIR/kyros-agent-workflow/src"
    echo "Epic build progress logged" > "$TEST_DIR/kyros-agent-workflow/claude-progress.txt"

    # Create epics directory with execution state
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: submitting
YAML

    cd "$TEST_DIR"
    git init -q
    git config user.email "test@test.com"
    git config user.name "Test"
    git add -A
    git commit -q -m "initial"
}

teardown() {
    rm -rf "$TEST_DIR"
}

@test "passes when all DoD criteria are met" {
    run bash "$SCRIPT" "$TEST_DIR/epics/v1" "data-loading"
    assert_success
    assert_output --partial "PASS"
}

@test "fails when TODO comments found in src" {
    echo '# TODO: fix this later' > "$TEST_DIR/kyros-agent-workflow/src/main.py"
    git -C "$TEST_DIR" add -A
    git -C "$TEST_DIR" commit -q -m "add src"

    run bash "$SCRIPT" "$TEST_DIR/epics/v1" "data-loading"
    assert_failure
    assert_output --partial "TODO"
}

@test "fails when uncommitted changes exist" {
    echo 'new file' > "$TEST_DIR/kyros-agent-workflow/src/new.py"

    run bash "$SCRIPT" "$TEST_DIR/epics/v1" "data-loading"
    assert_failure
    assert_output --partial "Uncommitted"
}

@test "fails when progress file is empty" {
    > "$TEST_DIR/kyros-agent-workflow/claude-progress.txt"
    git -C "$TEST_DIR" add -A
    git -C "$TEST_DIR" commit -q -m "empty progress"

    run bash "$SCRIPT" "$TEST_DIR/epics/v1" "data-loading"
    assert_failure
    assert_output --partial "claude-progress.txt"
}
```

**Step 3: Run all tests**

Run: `npx bats tests/*.bats`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add tests/session_start_test.bats tests/definition_of_done_test.bats
git commit -m "test: update session-start and definition-of-done tests for execution state model"
```

---

## Phase 5: Templates & Cleanup

### Task 14: Update `CLAUDE.md.template`

**Files:**
- Modify: `templates/CLAUDE.md.template`

**Step 1: Rewrite the template**

```markdown
# {{PROJECT_NAME}}

## Quick Start

You are working on a client analytics project governed by the one-shot-build harness.
Run `/status` to see where things stand.

## Workflow

This project follows a command-driven workflow:

1. **Profile Data** (`/profile-data`) — Automated data profiling
2. **Define Epics** (`/define-epics`) — Brainstorm and plan epics with the analyst
3. **Execute Plan** (`/execute-plan <epics-dir>`) — Build epics interactively
   - Or `/execute-plan-autonomously <epics-dir>` for fully autonomous execution

## Key Files

| File | Purpose |
|------|---------|
| `kyros-agent-workflow/claude-progress.txt` | Activity log |
| `kyros-agent-workflow/.harnessrc` | Project-specific config overrides |
| `kyros-agent-workflow/docs/context/data-profile-*.md` | Data profiling results |
| `<epics-dir>/*.yaml` | Epic definitions |
| `<epics-dir>/.execution-state.yaml` | Execution progress (created by execute-plan) |
| `kyros-agent-workflow/docs/standards/coding-standards.md` | Coding conventions |
| `kyros-agent-workflow/docs/standards/definition-of-done.md` | DoD checklist |
| `kyros-agent-workflow/docs/standards/review-criteria.md` | What the reviewer checks |

## Rules

- **One step at a time.** Complete the current step before starting the next.
- **Tests are immutable during build.** Do not modify test files written during planning.
- **Commit after every step.** Descriptive messages. Code must be production-quality at every commit.
- **Self-review before requesting review.** Check your own work first.

## Anti-Patterns (DO NOT)

- Modify tests to make them pass during build phase
- Work on multiple steps simultaneously
- Skip the review loop
- Refactor working code that isn't part of the current step
- Continue past completion signals
```

**Step 2: Commit**

```bash
git add templates/CLAUDE.md.template
git commit -m "refactor(template): update CLAUDE.md for command-driven workflow"
```

---

### Task 15: Update `.harnessrc.template`

**Files:**
- Modify: `templates/.harnessrc.template`

Remove the `execution.mode` field since mode is now determined by which command is used.

**Step 1: Remove the execution mode section**

In `templates/.harnessrc.template`, delete these lines:

```
# Execution environment
# execution:
#   mode: autonomous              # autonomous | interactive
```

**Step 2: Commit**

```bash
git add templates/.harnessrc.template
git commit -m "refactor(template): remove execution.mode from .harnessrc (now command-driven)"
```

---

### Task 16: Remove deprecated files

**Files:**
- Delete: `commands/next.md`
- Delete: `templates/project-state.yaml.template`

**Step 1: Remove the files**

```bash
git rm commands/next.md templates/project-state.yaml.template
```

**Step 2: Commit**

```bash
git commit -m "refactor: remove /next command and project-state.yaml template (replaced by explicit commands)"
```

---

### Task 17: Update `commands/status.md`

**Files:**
- Modify: `commands/status.md`

The status command now scans for execution states instead of reading global phase.

**Step 1: Rewrite `commands/status.md`**

```markdown
---
description: "Check workflow state: active executions, progress, and available commands."
disable-model-invocation: true
---

Check the current workflow state by doing the following:

1. **Scan for execution states:** Look for `.execution-state.yaml` files in the project (search recursively for files named `.execution-state.yaml`).

2. **For each execution state found:**
   - Read the file
   - Report: directory path, mode (interactive/autonomous), epic progress (N of M complete), current epic and step if in progress

3. **Check for data profiles:** Look for `kyros-agent-workflow/docs/context/data-profile-*.md` files. If found, list them.

4. **Check for epic directories:** Look for directories containing `.yaml` epic spec files. List any found.

5. **Present a summary** showing:
   - Active executions (if any)
   - Available data profiles (if any)
   - Defined epic directories (if any)
   - Suggested next command based on what exists

6. **Available commands reminder:**
   - `/init` — Scaffold a new project
   - `/profile-data` — Profile data tables
   - `/define-epics` — Brainstorm and define epics
   - `/execute-plan <dir>` — Execute epics interactively
   - `/execute-plan-autonomously <dir>` — Execute epics autonomously
   - `/board` — Open Kanban dashboard
   - `/prune-knowledge` — Review and cleanup solution docs
```

**Step 2: Commit**

```bash
git add commands/status.md
git commit -m "refactor(status): scan for execution states instead of global phase"
```

---

## Phase 6: Dashboard

### Task 18: Update dashboard to read execution state

**Files:**
- Modify: `dashboard/app.js`

The dashboard needs to read `.execution-state.yaml` instead of `project-state.yaml`. Add a directory selector when multiple execution states exist.

**Step 1: Update the state path and loading logic**

In `dashboard/app.js`, make the following changes:

1. Replace the `STATE_PATH` constant:
```javascript
// Old:
const STATE_PATH = '/project-state.yaml';
// New:
const DEFAULT_STATE_PATH = '/execution-states';  // API endpoint that returns available states
let STATE_PATH = '';  // Set dynamically after loading available states
```

2. Add a function to discover execution states. Since the dashboard is served by `serve.sh`, we need to update the serve script to expose execution state files. The simplest approach: update `STATE_PATH` to accept a query parameter and have the dashboard serve whichever `.execution-state.yaml` is requested.

**However**, this is a significant change to the dashboard's serving infrastructure. For the initial implementation, a simpler approach: update the dashboard to accept the execution state path as a URL parameter.

Replace the `STATE_PATH` constant with:
```javascript
const urlParams = new URLSearchParams(window.location.search);
const STATE_PATH = urlParams.get('state') || '/execution-state.yaml';
```

And update `dashboard/serve.sh` to serve the execution state file from the correct location (the user will pass the epics dir path when launching the board, or the board command will detect it).

**Note:** The full dashboard overhaul (directory selector, multiple state files) is a larger effort. For this task, update the dashboard to work with the new state file format. The column mapping in `normalizeStatus` already handles the new status values (`planning`, `building`, `submitting`, `completed`, `pending`).

The key change in `app.js` is updating how it reads epic data. The `.execution-state.yaml` format has epics at the top level (not nested under a `workflow` key), and the structure is slightly different. Update the `updateSummaryBar` function:

In `updateSummaryBar`, replace the project name and phase reading:
```javascript
// Old phase reading from workflow object:
const phase = (state.workflow && state.workflow.current_phase) || '—';
// New — no global phase concept, derive from epic statuses:
const epics = state.epics || {};
const epicNames = Object.keys(epics);
const inProgress = epicNames.find(k => !['completed', 'pending'].includes(epics[k].status));
const phase = inProgress ? epics[inProgress].status : (epicNames.every(k => epics[k].status === 'completed') ? 'done' : 'pending');
```

Replace the epic badge:
```javascript
// Old:
const epic = (state.workflow && state.workflow.current_epic) || '—';
// New:
const epic = inProgress || '—';
```

The `renderBoard` and card creation functions should work as-is since they already iterate over `state.epics` and handle the various statuses via `normalizeStatus`.

Add `submitting` to the `normalizeStatus` map:
```javascript
'submitting':  'review',
'planning':    'plan',
```

**Step 2: Commit**

```bash
git add dashboard/app.js
git commit -m "refactor(dashboard): read execution state format, derive phase from epic statuses"
```

---

## Phase 7: Final Verification

### Task 19: Run full test suite and verify

**Step 1: Run all BATS tests**

Run: `npx bats tests/*.bats`
Expected: All tests PASS

**Step 2: Verify no broken references**

Search for any remaining references to `/next` or `project-state.yaml` that should have been updated:

```bash
grep -rn "/next" commands/ skills/ hooks/ templates/ --include="*.md" --include="*.sh"
grep -rn "project-state.yaml" commands/ skills/ hooks/ templates/ lib/ --include="*.md" --include="*.sh" --include="*.js"
```

Fix any remaining references found.

**Step 3: Verify all new commands exist**

```bash
ls commands/profile-data.md commands/define-epics.md commands/execute-plan.md commands/execute-plan-autonomously.md
```
Expected: All four files exist.

**Step 4: Verify execute-plan skill exists**

```bash
ls skills/execute-plan/SKILL.md
```
Expected: File exists.

**Step 5: Final commit (if any fixes were needed)**

```bash
git add -A
git commit -m "fix: resolve remaining references to old workflow model"
```

---

## Summary of All Tasks

| # | Task | Phase |
|---|------|-------|
| 1 | Refactor `lib/state.sh` — add execution state helpers | Foundation |
| 2 | Add tests for execution state functions | Foundation |
| 3 | Create new command files (4 files) | Commands |
| 4 | Refactor `gather-context` skill for `/profile-data` | Skills |
| 5 | Refactor `define-epics` skill with brainstorming flow | Skills |
| 6 | Refactor `plan-epic` skill to accept parameters | Skills |
| 7 | Refactor `build-step` skill to accept parameters | Skills |
| 8 | Refactor `submit-epic` skill to accept parameters | Skills |
| 9 | Create `execute-plan` orchestrator skill | Skills |
| 10 | Refactor `session-start.sh` for execution state | Hooks |
| 11 | Refactor `definition-of-done.sh` to accept epics dir | Hooks |
| 12 | Verify `self-check.sh` (no changes needed) | Hooks |
| 13 | Update BATS tests for new state model | Hooks |
| 14 | Update `CLAUDE.md.template` | Templates |
| 15 | Update `.harnessrc.template` | Templates |
| 16 | Remove `commands/next.md` and `project-state.yaml.template` | Cleanup |
| 17 | Update `commands/status.md` | Cleanup |
| 18 | Update dashboard for execution state | Dashboard |
| 19 | Run full test suite and verify | Verification |
