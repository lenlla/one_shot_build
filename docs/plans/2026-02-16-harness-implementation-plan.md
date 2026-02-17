# One-Shot Build Harness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Claude Code plugin that governs the agent's development workflow across client predictive modeling projects, with skills for each phase, enforcement hooks, agent team coordination, and project scaffolding.

**Architecture:** A Claude Code plugin (skills + hooks + agents + commands + templates) installed per developer. The `/init` skill scaffolds per-project repos from templates. Skills guide each workflow phase. Hooks enforce quality gates mechanically. Agent teams coordinate the build/review loop.

**Tech Stack:** Bash (hooks, enforcement scripts, state library), Markdown (skills, agents, commands), YAML (state, templates), JSON (plugin config, hooks config), BATS (shell script tests)

**Design doc:** `docs/plans/2026-02-16-harness-architecture-design.md`

---

## Epic 1: Plugin Foundation

### Task 1.1: Create plugin manifest

**Files:**
- Create: `.claude-plugin/plugin.json`

**Step 1: Create plugin manifest**

```json
{
  "name": "one-shot-build",
  "description": "Workflow harness for autonomous client analytics project execution with Claude Code",
  "version": "0.1.0",
  "author": {
    "name": "Len Llaguno"
  },
  "repository": "https://github.com/lenlla/one_shot_build",
  "license": "MIT",
  "keywords": ["harness", "workflow", "analytics", "agent-teams", "tdd", "review"]
}
```

**Step 2: Verify plugin structure recognized**

Run: `ls .claude-plugin/plugin.json`
Expected: File exists

**Step 3: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -m "feat: add plugin manifest for one-shot-build"
```

### Task 1.2: Create plugin directory structure

**Files:**
- Create directories: `skills/`, `hooks/`, `commands/`, `agents/`, `templates/`, `lib/`, `tests/`

**Step 1: Create all plugin directories**

```bash
mkdir -p skills hooks commands agents templates lib tests
```

**Step 2: Add .gitkeep files to empty directories**

```bash
touch skills/.gitkeep hooks/.gitkeep commands/.gitkeep agents/.gitkeep templates/.gitkeep lib/.gitkeep tests/.gitkeep
```

**Step 3: Commit**

```bash
git add skills/ hooks/ commands/ agents/ templates/ lib/ tests/
git commit -m "feat: scaffold plugin directory structure"
```

---

## Epic 2: State Library

The state library provides bash utilities for reading and updating `project-state.yaml`. This is the foundation everything else depends on.

### Task 2.1: Write failing tests for state library

**Files:**
- Create: `tests/state_test.bats`

**Step 1: Install BATS test framework**

```bash
npm init -y
npm install --save-dev bats bats-support bats-assert
```

**Step 2: Write tests for state library**

```bash
#!/usr/bin/env bats
# tests/state_test.bats

setup() {
    load 'node_modules/bats-support/load'
    load 'node_modules/bats-assert/load'

    TEST_DIR="$(mktemp -d)"
    export PROJECT_ROOT="$TEST_DIR"

    # Source the library
    source "${BATS_TEST_DIRNAME}/../lib/state.sh"
}

teardown() {
    rm -rf "$TEST_DIR"
}

# --- read_state tests ---

@test "read_state returns empty string when no state file exists" {
    run read_state "workflow.current_phase"
    assert_success
    assert_output ""
}

@test "read_state reads current phase from state file" {
    cat > "$PROJECT_ROOT/project-state.yaml" <<'YAML'
project:
  name: "Test Project"
workflow:
  current_phase: "gather_context"
  current_epic: ""
  current_step: ""
YAML
    run read_state "workflow.current_phase"
    assert_success
    assert_output "gather_context"
}

@test "read_state reads nested epic status" {
    cat > "$PROJECT_ROOT/project-state.yaml" <<'YAML'
project:
  name: "Test Project"
workflow:
  current_phase: "build"
  current_epic: "01-data-loading"
epics:
  01-data-loading:
    status: in_progress
YAML
    run read_state "epics.01-data-loading.status"
    assert_success
    assert_output "in_progress"
}

# --- update_state tests ---

@test "update_state sets a value in the state file" {
    cat > "$PROJECT_ROOT/project-state.yaml" <<'YAML'
workflow:
  current_phase: "gather_context"
YAML
    run update_state "workflow.current_phase" "define_epics"
    assert_success

    run read_state "workflow.current_phase"
    assert_output "define_epics"
}

# --- get_current_phase tests ---

@test "get_current_phase returns the current workflow phase" {
    cat > "$PROJECT_ROOT/project-state.yaml" <<'YAML'
workflow:
  current_phase: "build"
YAML
    run get_current_phase
    assert_success
    assert_output "build"
}

# --- get_current_epic tests ---

@test "get_current_epic returns the current epic" {
    cat > "$PROJECT_ROOT/project-state.yaml" <<'YAML'
workflow:
  current_epic: "02-data-translation"
YAML
    run get_current_epic
    assert_success
    assert_output "02-data-translation"
}

# --- get_current_step tests ---

@test "get_current_step returns the current step" {
    cat > "$PROJECT_ROOT/project-state.yaml" <<'YAML'
workflow:
  current_step: "step-03-type-casting"
YAML
    run get_current_step
    assert_success
    assert_output "step-03-type-casting"
}

# --- log_progress tests ---

@test "log_progress appends to claude-progress.txt" {
    run log_progress "Completed step-01 implementation"
    assert_success

    run cat "$PROJECT_ROOT/claude-progress.txt"
    assert_output --partial "Completed step-01 implementation"
}

@test "log_progress includes timestamp" {
    run log_progress "Test message"
    assert_success

    run cat "$PROJECT_ROOT/claude-progress.txt"
    # Should contain ISO-like timestamp
    assert_output --regexp "[0-9]{4}-[0-9]{2}-[0-9]{2}"
}
```

**Step 3: Run tests to verify they fail**

Run: `npx bats tests/state_test.bats`
Expected: FAIL (lib/state.sh does not exist yet)

**Step 4: Commit**

```bash
git add tests/state_test.bats package.json package-lock.json
git commit -m "test: add failing tests for state library"
```

### Task 2.2: Implement state library

**Files:**
- Create: `lib/state.sh`

**Step 1: Implement state library**

```bash
#!/usr/bin/env bash
# lib/state.sh — Utilities for reading/updating project-state.yaml
# Requires: yq (https://github.com/mikefarah/yq) or falls back to grep/sed

set -euo pipefail

# Determine project root (where project-state.yaml lives)
# Can be overridden by setting PROJECT_ROOT before sourcing
PROJECT_ROOT="${PROJECT_ROOT:-$(pwd)}"

STATE_FILE="${PROJECT_ROOT}/project-state.yaml"
PROGRESS_FILE="${PROJECT_ROOT}/claude-progress.txt"

# --- Core YAML operations ---

# Read a dot-separated path from the state file
# Usage: read_state "workflow.current_phase"
read_state() {
    local path="$1"

    if [[ ! -f "$STATE_FILE" ]]; then
        echo ""
        return 0
    fi

    # Convert dot path to yq path: workflow.current_phase -> .workflow.current_phase
    local yq_path=".${path}"

    if command -v yq &>/dev/null; then
        local result
        result=$(yq eval "$yq_path" "$STATE_FILE" 2>/dev/null || echo "")
        # yq returns "null" for missing keys
        if [[ "$result" == "null" ]]; then
            echo ""
        else
            echo "$result"
        fi
    else
        # Fallback: simple grep-based extraction for flat keys
        # This only works for simple key: value pairs, not nested structures
        local key="${path##*.}"
        grep -E "^\s*${key}:" "$STATE_FILE" 2>/dev/null | head -1 | sed 's/.*:\s*//' | tr -d '"' | tr -d "'" || echo ""
    fi
}

# Update a dot-separated path in the state file
# Usage: update_state "workflow.current_phase" "build"
update_state() {
    local path="$1"
    local value="$2"

    if [[ ! -f "$STATE_FILE" ]]; then
        echo "Error: State file not found at $STATE_FILE" >&2
        return 1
    fi

    local yq_path=".${path}"

    if command -v yq &>/dev/null; then
        yq eval -i "${yq_path} = \"${value}\"" "$STATE_FILE"
    else
        echo "Error: yq is required for state updates. Install from https://github.com/mikefarah/yq" >&2
        return 1
    fi
}

# --- Convenience functions ---

get_current_phase() {
    read_state "workflow.current_phase"
}

get_current_epic() {
    read_state "workflow.current_epic"
}

get_current_step() {
    read_state "workflow.current_step"
}

# Append a timestamped entry to the progress file
# Usage: log_progress "Completed step-01 implementation"
log_progress() {
    local message="$1"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%d %H:%M:%S")

    echo "[${timestamp}] ${message}" >> "$PROGRESS_FILE"
}
```

**Step 2: Run tests to verify they pass**

Run: `npx bats tests/state_test.bats`
Expected: All tests PASS (requires `yq` installed)

**Step 3: Commit**

```bash
git add lib/state.sh
git commit -m "feat: implement state library for project-state.yaml operations"
```

---

## Epic 3: Templates

### Task 3.1: Create CLAUDE.md template

**Files:**
- Create: `templates/CLAUDE.md.template`

**Step 1: Write the template**

This template generates a ~100-line CLAUDE.md that acts as a table of contents, not a manual.

```markdown
# {{PROJECT_NAME}}

## Quick Start

You are working on a client analytics project governed by the one-shot-build harness.
Run `/status` to see where things stand. Run `/next` to advance.

## Current State

Read `project-state.yaml` for the canonical workflow state.
Read `claude-progress.txt` for a log of what's been done.

## Workflow

This project follows a phased workflow. You must complete each phase before advancing:

1. **Gather Context** (`/gather-context`) — Profile data, Q&A with analyst
2. **Define Epics** (`/define-epics`) — Collaboratively break down the project
3. **Plan Epic** (`/plan-epic`) — TDD planning for each epic
4. **Build** (`/build`) — Agent team: developer + reviewer
5. **Submit** (`/submit`) — PR + advance to next epic

## Key Files

| File | Purpose |
|------|---------|
| `project-state.yaml` | Workflow state (phase, epic, step) |
| `claude-progress.txt` | Activity log |
| `.harnessrc` | Project-specific config overrides |
| `docs/context/data-profile.md` | Data exploration results |
| `docs/context/analyst-notes.md` | Analyst Q&A outcomes |
| `docs/epics/*.yaml` | Epic definitions |
| `docs/standards/coding-standards.md` | Coding conventions |
| `docs/standards/definition-of-done.md` | DoD checklist |
| `docs/standards/review-criteria.md` | What the reviewer checks |
| `config/project-config.yaml` | Human decisions (mappings, predictors, etc.) |

## Rules

- **One step at a time.** Complete the current step before starting the next.
- **Tests are immutable during build.** Do not modify test files written during planning.
- **Commit after every step.** Descriptive messages. Code must be production-quality at every commit.
- **Self-review before requesting review.** Check your own work first.
- **Emit structured status blocks** after completing each step (see `docs/standards/status-block-format.md`).

## Anti-Patterns (DO NOT)

- Modify tests to make them pass during build phase
- Work on multiple steps simultaneously
- Skip the review loop
- Refactor working code that isn't part of the current step
- Continue past completion signals
- Probe data shapes without validation — use typed boundaries

## Standards

See `docs/standards/` for:
- `coding-standards.md` — Style, conventions, shared utilities
- `definition-of-done.md` — What "done" means for each step
- `review-criteria.md` — What the reviewer checks
```

**Step 2: Commit**

```bash
git add templates/CLAUDE.md.template
git commit -m "feat: add CLAUDE.md template (~100 lines, table of contents)"
```

### Task 3.2: Create project-state.yaml template

**Files:**
- Create: `templates/project-state.yaml.template`

**Step 1: Write the template**

```yaml
# Project State — Canonical workflow state for {{PROJECT_NAME}}
# This file is the source of truth. Updated by the harness after each gate.

project:
  name: "{{PROJECT_NAME}}"
  created: "{{CREATED_DATE}}"

workflow:
  current_phase: "gather_context"
  current_epic: ""
  current_step: ""

phases:
  gather_context:
    status: pending
    completed_at: null
    artifacts: []
  define_epics:
    status: pending
    completed_at: null

epics: {}

circuit_breaker:
  state: "CLOSED"
  no_progress_count: 0
  same_error_count: 0
  last_error: ""
```

**Step 2: Commit**

```bash
git add templates/project-state.yaml.template
git commit -m "feat: add project-state.yaml template with initial workflow state"
```

### Task 3.3: Create standards templates

**Files:**
- Create: `templates/definition-of-done.md.template`
- Create: `templates/review-criteria.md.template`
- Create: `templates/coding-standards.md.template`

**Step 1: Write definition-of-done template**

```markdown
# Definition of Done

A step is "done" when ALL of the following are true:

## Per Step
- [ ] Tests pass (full test suite, not just new tests)
- [ ] Lint clean (no warnings or errors)
- [ ] Test files unmodified since TDD phase
- [ ] Code committed with descriptive message
- [ ] Structured status block emitted
- [ ] Git shows file changes (verified by hook)
- [ ] Review agent approved

## Per Epic (before PR submission)
- [ ] All steps marked completed in project-state.yaml
- [ ] All steps have tests_pass: true AND review_approved: true
- [ ] claude-progress.txt updated with epic summary
- [ ] No TODO comments in code
- [ ] No debug print statements
- [ ] No unused imports
- [ ] Shared utilities used (no hand-rolled helpers for common operations)
- [ ] project-state.yaml is current and committed
```

**Step 2: Write review-criteria template**

```markdown
# Review Criteria

The review agent checks each step against these criteria.

## Must Pass (blocking)
1. **Acceptance criteria met** — Does the implementation satisfy the step spec?
2. **Tests pass** — Full test suite, not just the new tests for this step
3. **Test immutability** — No test files modified during build phase
4. **No regressions** — Existing functionality still works
5. **Coding standards** — Follows project conventions (see coding-standards.md)

## Should Pass (flag but don't block)
6. **Shared utilities** — Uses centralized utilities instead of hand-rolled helpers
7. **Typed boundaries** — Data shapes validated at module boundaries
8. **Commit quality** — Descriptive message, focused diff, no unrelated changes
9. **Production quality** — No TODOs, debug prints, commented-out code

## Anti-Pattern Detection
- Test-only loops (running tests repeatedly without code changes)
- Feature creep (implementing beyond the step spec)
- Refactoring working code outside the current step scope
```

**Step 3: Write coding-standards template**

```markdown
# Coding Standards

## Python / PySpark

### Style
- Follow PEP 8
- Use type hints for function signatures
- Maximum line length: 120 characters
- Use f-strings for string formatting

### Structure
- One module per logical concern
- Shared utilities go in `src/utils/` — do NOT hand-roll helpers
- Validate data shapes at module boundaries with explicit schema checks
- Use descriptive variable names (no single-letter variables except loop counters)

### Testing
- Tests live in `tests/` mirroring `src/` structure
- Test file names: `test_<module_name>.py`
- Use pytest fixtures for shared setup
- Each test tests ONE behavior
- Tests are written during planning phase and are IMMUTABLE during build

### PySpark Specific
- Use DataFrame API over SQL strings where possible
- Define schemas explicitly (StructType) for data validation
- Cache DataFrames only when reused multiple times
- Use `.explain()` to verify query plans during development

### Commits
- One logical change per commit
- Message format: `<type>: <description>` (feat, fix, test, refactor, docs)
- Include the step name in the message when relevant
```

**Step 4: Commit**

```bash
git add templates/definition-of-done.md.template templates/review-criteria.md.template templates/coding-standards.md.template
git commit -m "feat: add standards templates (DoD, review criteria, coding standards)"
```

### Task 3.4: Create .harnessrc template

**Files:**
- Create: `templates/.harnessrc.template`

**Step 1: Write the template**

```yaml
# .harnessrc — Per-project configuration overrides for one-shot-build harness
# All values below are defaults. Uncomment and modify to override.

# Circuit breaker thresholds
# circuit_breaker:
#   no_progress_threshold: 3
#   same_error_threshold: 5
#   max_review_rounds: 5
#   output_decline_threshold: 70
#   permission_denial_threshold: 2

# Rate limiting
# rate_limit:
#   max_calls_per_hour: 100

# Agent team configuration
# agent_team:
#   developer_model: "sonnet"
#   reviewer_model: "sonnet"

# Testing
# testing:
#   test_command: "pytest tests/ -v"
#   lint_command: "ruff check src/ tests/"
#   format_command: "ruff format src/ tests/"
```

**Step 2: Commit**

```bash
git add templates/.harnessrc.template
git commit -m "feat: add .harnessrc template for per-project config overrides"
```

---

## Epic 4: Init Skill + Command

### Task 4.1: Create the harness-init skill

**Files:**
- Create: `skills/harness-init/SKILL.md`

**Step 1: Write the skill**

```markdown
---
name: harness-init
description: Use when starting a new client analytics project. Scaffolds project structure from templates with workflow state, standards docs, and CLAUDE.md.
---

# Initialize Project

## Overview

Scaffold a new client analytics project with the one-shot-build harness structure.

## Process

1. **Ask project name** — Use AskUserQuestion to get the project name
2. **Create directory structure** — Create all required directories
3. **Generate files from templates** — Replace `{{PROJECT_NAME}}` and `{{CREATED_DATE}}` placeholders
4. **Initialize git** — If not already a git repo, initialize one
5. **Create initial commit** — Commit the scaffolded structure
6. **Update state** — Set workflow phase to `gather_context`

## Directory Structure to Create

```
├── CLAUDE.md
├── project-state.yaml
├── claude-progress.txt
├── .harnessrc
├── docs/
│   ├── context/
│   ├── epics/
│   ├── standards/
│   │   ├── coding-standards.md
│   │   ├── definition-of-done.md
│   │   └── review-criteria.md
│   └── plans/
├── config/
├── src/
│   └── utils/
├── tests/
└── scripts/
```

## Template Processing

For each template in the plugin's `templates/` directory:
1. Read the template file
2. Replace `{{PROJECT_NAME}}` with the user-provided project name
3. Replace `{{CREATED_DATE}}` with today's date in ISO format (YYYY-MM-DD)
4. Write to the corresponding path in the project root

Template mapping:
- `templates/CLAUDE.md.template` → `CLAUDE.md`
- `templates/project-state.yaml.template` → `project-state.yaml`
- `templates/definition-of-done.md.template` → `docs/standards/definition-of-done.md`
- `templates/review-criteria.md.template` → `docs/standards/review-criteria.md`
- `templates/coding-standards.md.template` → `docs/standards/coding-standards.md`
- `templates/.harnessrc.template` → `.harnessrc`

## After Scaffolding

Create an empty `claude-progress.txt` with a header line:

```
# Claude Progress Log — {{PROJECT_NAME}}
```

Log the initialization:

```
[timestamp] Project initialized with one-shot-build harness. Phase: gather_context.
```

## Completion

Tell the user: "Project scaffolded. Run `/gather-context` to begin data profiling and analyst Q&A."
```

**Step 2: Commit**

```bash
git add skills/harness-init/SKILL.md
git commit -m "feat: add harness-init skill for project scaffolding"
```

### Task 4.2: Create the /init command

**Files:**
- Create: `commands/init.md`

**Step 1: Write the command**

```markdown
---
description: "Scaffold a new client analytics project with the one-shot-build harness structure."
disable-model-invocation: true
---

Invoke the one-shot-build:harness-init skill and follow it exactly as presented to you
```

**Step 2: Commit**

```bash
git add commands/init.md
git commit -m "feat: add /init command shorthand for harness-init skill"
```

---

## Epic 5: Session Start Hook

### Task 5.1: Write failing tests for session-start hook

**Files:**
- Create: `tests/session_start_test.bats`

**Step 1: Write tests**

```bash
#!/usr/bin/env bats
# tests/session_start_test.bats

setup() {
    load 'node_modules/bats-support/load'
    load 'node_modules/bats-assert/load'

    TEST_DIR="$(mktemp -d)"
    export PROJECT_ROOT="$TEST_DIR"

    SCRIPT_DIR="${BATS_TEST_DIRNAME}/../hooks"
}

teardown() {
    rm -rf "$TEST_DIR"
}

@test "session-start outputs valid JSON" {
    # Create a minimal state file
    cat > "$TEST_DIR/project-state.yaml" <<'YAML'
workflow:
  current_phase: "gather_context"
  current_epic: ""
  current_step: ""
YAML

    cd "$TEST_DIR"
    run bash "${SCRIPT_DIR}/session-start.sh"
    assert_success

    # Should be valid JSON (check for hookSpecificOutput key)
    assert_output --partial "hookSpecificOutput"
}

@test "session-start includes current phase in output" {
    cat > "$TEST_DIR/project-state.yaml" <<'YAML'
workflow:
  current_phase: "build"
  current_epic: "01-data-loading"
  current_step: "step-02-schema"
YAML

    cd "$TEST_DIR"
    run bash "${SCRIPT_DIR}/session-start.sh"
    assert_success
    assert_output --partial "build"
    assert_output --partial "01-data-loading"
}

@test "session-start handles missing state file gracefully" {
    cd "$TEST_DIR"
    run bash "${SCRIPT_DIR}/session-start.sh"
    assert_success
    assert_output --partial "hookSpecificOutput"
    assert_output --partial "No project-state.yaml found"
}
```

**Step 2: Run tests to verify they fail**

Run: `npx bats tests/session_start_test.bats`
Expected: FAIL (hooks/session-start.sh does not exist)

**Step 3: Commit**

```bash
git add tests/session_start_test.bats
git commit -m "test: add failing tests for session-start hook"
```

### Task 5.2: Implement session-start hook

**Files:**
- Create: `hooks/session-start.sh`

**Step 1: Write the hook script**

```bash
#!/usr/bin/env bash
# hooks/session-start.sh — Reads project-state.yaml and injects workflow context
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

if [[ -f "$STATE_FILE" ]]; then
    phase=$(get_current_phase)
    epic=$(get_current_epic)
    step=$(get_current_step)

    context="## One-Shot Build Harness Active\\n\\n"
    context+="**Current Phase:** ${phase:-not set}\\n"

    if [[ -n "$epic" ]]; then
        context+="**Current Epic:** ${epic}\\n"
    fi
    if [[ -n "$step" ]]; then
        context+="**Current Step:** ${step}\\n"
    fi

    context+="\\n**Next action:** "
    case "$phase" in
        gather_context)
            context+="Run \`/gather-context\` to begin data profiling and analyst Q&A."
            ;;
        define_epics)
            context+="Run \`/define-epics\` to collaboratively break down the project into epics."
            ;;
        plan)
            context+="Run \`/plan-epic\` to create a TDD plan for epic ${epic}."
            ;;
        build)
            context+="Run \`/build\` to start the agent team build/review loop for ${epic} / ${step}."
            ;;
        submit)
            context+="Run \`/submit\` to submit a PR for epic ${epic}."
            ;;
        *)
            context+="Run \`/status\` to check workflow state."
            ;;
    esac

    context+="\\n\\nRead \`project-state.yaml\` for full state. Read \`CLAUDE.md\` for project guide."
else
    context="## One-Shot Build Harness\\n\\n"
    context+="No project-state.yaml found in the current directory.\\n"
    context+="If this is a new project, run \`/init\` to scaffold it.\\n"
    context+="If this is an existing project, navigate to its root directory."
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

**Step 2: Make executable**

```bash
chmod +x hooks/session-start.sh
```

**Step 3: Run tests to verify they pass**

Run: `npx bats tests/session_start_test.bats`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add hooks/session-start.sh
git commit -m "feat: implement session-start hook with state-aware context injection"
```

### Task 5.3: Create hooks.json configuration

**Files:**
- Create: `hooks/hooks.json`

**Step 1: Write the hooks config**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume|clear|compact",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh",
            "async": false
          }
        ]
      }
    ]
  }
}
```

Note: `TaskCompleted` and `TeammateIdle` hooks will be added in Epic 7 after the enforcement scripts are built.

**Step 2: Commit**

```bash
git add hooks/hooks.json
git commit -m "feat: add hooks.json with SessionStart configuration"
```

---

## Epic 6: Status Skill + Command

### Task 6.1: Create the harness-status skill

**Files:**
- Create: `skills/harness-status/SKILL.md`

**Step 1: Write the skill**

```markdown
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
```

**Step 2: Commit**

```bash
git add skills/harness-status/SKILL.md
git commit -m "feat: add harness-status skill for workflow state display"
```

### Task 6.2: Create the /status command

**Files:**
- Create: `commands/status.md`

**Step 1: Write the command**

```markdown
---
description: "Check current workflow state: phase, epic, step, gates, and next action."
disable-model-invocation: true
---

Invoke the one-shot-build:harness-status skill and follow it exactly as presented to you
```

**Step 2: Commit**

```bash
git add commands/status.md
git commit -m "feat: add /status command shorthand"
```

---

## Epic 7: Enforcement Scripts

### Task 7.1: Write failing tests for test-immutability check

**Files:**
- Create: `tests/check_test_immutability_test.bats`

**Step 1: Write tests**

```bash
#!/usr/bin/env bats
# tests/check_test_immutability_test.bats

setup() {
    load 'node_modules/bats-support/load'
    load 'node_modules/bats-assert/load'

    TEST_DIR="$(mktemp -d)"
    cd "$TEST_DIR"

    # Initialize a git repo
    git init -q
    git config user.email "test@test.com"
    git config user.name "Test"

    # Create initial test file and commit (simulates TDD phase)
    mkdir -p tests
    echo 'def test_example(): assert True' > tests/test_example.py
    git add tests/test_example.py
    git commit -q -m "test: add tests (TDD phase)"

    # Tag the TDD commit so the script can reference it
    git tag tdd-baseline

    SCRIPT="${BATS_TEST_DIRNAME}/../hooks/check-test-immutability.sh"
}

teardown() {
    rm -rf "$TEST_DIR"
}

@test "passes when test files are unchanged since TDD baseline" {
    # No changes to test files
    run bash "$SCRIPT" tdd-baseline
    assert_success
    assert_output --partial "PASS"
}

@test "fails when a test file is modified during build" {
    # Modify a test file
    echo 'def test_example(): assert False' > tests/test_example.py
    git add tests/test_example.py

    run bash "$SCRIPT" tdd-baseline
    assert_failure
    assert_output --partial "FAIL"
    assert_output --partial "test_example.py"
}

@test "passes when only src files are modified" {
    # Add/modify a source file, leave tests alone
    mkdir -p src
    echo 'def hello(): return "world"' > src/main.py
    git add src/main.py

    run bash "$SCRIPT" tdd-baseline
    assert_success
}

@test "fails when a new test file is added during build" {
    # Add a new test file (not allowed during build)
    echo 'def test_new(): assert True' > tests/test_new.py
    git add tests/test_new.py

    run bash "$SCRIPT" tdd-baseline
    assert_failure
    assert_output --partial "test_new.py"
}
```

**Step 2: Run tests to verify they fail**

Run: `npx bats tests/check_test_immutability_test.bats`
Expected: FAIL

**Step 3: Commit**

```bash
git add tests/check_test_immutability_test.bats
git commit -m "test: add failing tests for test-immutability enforcement"
```

### Task 7.2: Implement test-immutability check

**Files:**
- Create: `hooks/check-test-immutability.sh`

**Step 1: Write the script**

```bash
#!/usr/bin/env bash
# hooks/check-test-immutability.sh
# Checks that no test files have been modified since the TDD baseline commit.
# Usage: check-test-immutability.sh <baseline-ref>
# Exit 0 = PASS (no test modifications)
# Exit 1 = FAIL (test files were modified)

set -euo pipefail

BASELINE_REF="${1:-tdd-baseline}"

# Get list of test files changed since baseline
changed_tests=$(git diff --name-only "$BASELINE_REF" -- 'tests/' '*/tests/' '**/test_*' '**/*_test.*' 2>/dev/null || echo "")

# Also check staged changes
staged_tests=$(git diff --cached --name-only "$BASELINE_REF" -- 'tests/' '*/tests/' '**/test_*' '**/*_test.*' 2>/dev/null || echo "")

# Combine and deduplicate
all_changed=$(echo -e "${changed_tests}\n${staged_tests}" | sort -u | grep -v '^$' || true)

if [[ -z "$all_changed" ]]; then
    echo "PASS: No test files modified since TDD baseline ($BASELINE_REF)"
    exit 0
else
    echo "FAIL: Test files modified during build phase (baseline: $BASELINE_REF)"
    echo ""
    echo "Modified test files:"
    echo "$all_changed" | while read -r file; do
        echo "  - $file"
    done
    echo ""
    echo "Tests are immutable during the build phase. If tests need to change,"
    echo "go back to the planning phase (/plan-epic) to update them."
    exit 1
fi
```

**Step 2: Make executable**

```bash
chmod +x hooks/check-test-immutability.sh
```

**Step 3: Run tests to verify they pass**

Run: `npx bats tests/check_test_immutability_test.bats`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add hooks/check-test-immutability.sh
git commit -m "feat: implement test-immutability enforcement script"
```

### Task 7.3: Write failing tests for definition-of-done check

**Files:**
- Create: `tests/definition_of_done_test.bats`

**Step 1: Write tests**

```bash
#!/usr/bin/env bats
# tests/definition_of_done_test.bats

setup() {
    load 'node_modules/bats-support/load'
    load 'node_modules/bats-assert/load'

    TEST_DIR="$(mktemp -d)"
    export PROJECT_ROOT="$TEST_DIR"

    SCRIPT="${BATS_TEST_DIRNAME}/../hooks/definition-of-done.sh"

    # Create minimal project structure
    mkdir -p "$TEST_DIR/tests" "$TEST_DIR/src"
    echo "" > "$TEST_DIR/claude-progress.txt"

    # Create state file with completed steps
    cat > "$TEST_DIR/project-state.yaml" <<'YAML'
workflow:
  current_phase: "submit"
  current_epic: "01-data-loading"
epics:
  01-data-loading:
    status: in_progress
    steps:
      step-01:
        status: completed
        tests_pass: true
        review_approved: true
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
    run bash "$SCRIPT"
    assert_success
    assert_output --partial "PASS"
}

@test "fails when state file has unapproved steps" {
    cat > "$TEST_DIR/project-state.yaml" <<'YAML'
workflow:
  current_phase: "submit"
  current_epic: "01-data-loading"
epics:
  01-data-loading:
    status: in_progress
    steps:
      step-01:
        status: completed
        tests_pass: true
        review_approved: false
YAML

    run bash "$SCRIPT"
    assert_failure
    assert_output --partial "review_approved"
}

@test "fails when TODO comments found in src" {
    echo '# TODO: fix this later' > "$TEST_DIR/src/main.py"
    git -C "$TEST_DIR" add -A
    git -C "$TEST_DIR" commit -q -m "add src"

    run bash "$SCRIPT"
    assert_failure
    assert_output --partial "TODO"
}
```

**Step 2: Run tests to verify they fail**

Run: `npx bats tests/definition_of_done_test.bats`
Expected: FAIL

**Step 3: Commit**

```bash
git add tests/definition_of_done_test.bats
git commit -m "test: add failing tests for definition-of-done check"
```

### Task 7.4: Implement definition-of-done check

**Files:**
- Create: `hooks/definition-of-done.sh`

**Step 1: Write the script**

```bash
#!/usr/bin/env bash
# hooks/definition-of-done.sh
# Runs the Definition of Done checklist before PR submission.
# Exit 0 = PASS, Exit 1 = FAIL with details

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source state library
source "${PLUGIN_ROOT}/lib/state.sh"

failures=()

# --- Check 1: All steps have tests_pass: true and review_approved: true ---
epic=$(get_current_epic)

if command -v yq &>/dev/null && [[ -f "$STATE_FILE" ]]; then
    # Check for any steps without tests_pass: true
    unapproved=$(yq eval ".epics.${epic}.steps | to_entries | .[] | select(.value.tests_pass != true or .value.review_approved != true) | .key" "$STATE_FILE" 2>/dev/null || echo "")
    if [[ -n "$unapproved" ]]; then
        failures+=("Steps missing tests_pass or review_approved: $unapproved")
    fi
fi

# --- Check 2: No TODO comments in src/ ---
if [[ -d "src" ]]; then
    todos=$(grep -rn "TODO\|FIXME\|HACK\|XXX" src/ 2>/dev/null || true)
    if [[ -n "$todos" ]]; then
        failures+=("TODO/FIXME comments found in src/:\n$todos")
    fi
fi

# --- Check 3: No debug print statements ---
if [[ -d "src" ]]; then
    debug_prints=$(grep -rn "print(" src/ --include="*.py" 2>/dev/null | grep -v "# noqa" || true)
    if [[ -n "$debug_prints" ]]; then
        failures+=("Debug print() statements found in src/:\n$debug_prints")
    fi
fi

# --- Check 4: claude-progress.txt exists and is non-empty ---
if [[ ! -s "$PROGRESS_FILE" ]]; then
    failures+=("claude-progress.txt is empty or missing")
fi

# --- Check 5: No uncommitted changes ---
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    failures+=("Uncommitted changes detected. Commit all work before submitting.")
fi

# --- Report ---
if [[ ${#failures[@]} -eq 0 ]]; then
    echo "PASS: All Definition of Done criteria met for epic ${epic}"
    exit 0
else
    echo "FAIL: Definition of Done check failed for epic ${epic}"
    echo ""
    for fail in "${failures[@]}"; do
        echo -e "  - $fail"
    done
    echo ""
    echo "Fix these issues before running /submit."
    exit 1
fi
```

**Step 2: Make executable**

```bash
chmod +x hooks/definition-of-done.sh
```

**Step 3: Run tests to verify they pass**

Run: `npx bats tests/definition_of_done_test.bats`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add hooks/definition-of-done.sh
git commit -m "feat: implement definition-of-done enforcement script"
```

---

## Epic 8: Agent Definitions

### Task 8.1: Create reviewer agent

**Files:**
- Create: `agents/reviewer.md`

**Step 1: Write the reviewer agent definition**

```markdown
---
name: reviewer
description: |
  Use this agent to review completed build steps against acceptance criteria, coding standards, and test immutability. This reviewer is adversarial — its job is to catch problems, not approve by default.
model: inherit
---

You are a strict code reviewer for a client analytics project. Your job is to catch problems. Do NOT approve work that doesn't meet ALL criteria.

## What You Check

For each completed step, verify:

### Blocking (must fix before approval)
1. **Acceptance criteria** — Read the step spec in `docs/epics/`. Does the implementation satisfy every criterion?
2. **Tests pass** — Run the FULL test suite, not just new tests. Command is in `.harnessrc` or default `pytest tests/ -v`.
3. **Test immutability** — Run `check-test-immutability.sh tdd-baseline`. Tests written during planning MUST NOT be modified.
4. **No regressions** — Verify existing functionality still works.
5. **Coding standards** — Check against `docs/standards/coding-standards.md`.

### Non-blocking (flag but approve if minor)
6. **Shared utilities** — Developer should use `src/utils/` instead of hand-rolling helpers.
7. **Typed boundaries** — Data shapes should be validated at module boundaries.
8. **Commit quality** — Descriptive message, focused diff, no unrelated changes.
9. **No TODOs/debug prints** — Clean code only.

## Anti-Patterns to Watch For
- Developer modified test files to make tests pass (CRITICAL — always reject)
- Test-only loops (running tests repeatedly without code changes)
- Feature creep (implementing beyond the step spec)
- Refactoring code outside the current step's scope

## How to Respond

If ALL blocking criteria pass:
- Message the developer: "Approved. [brief summary of what looks good]"
- Mark the task as approved

If ANY blocking criteria fail:
- Message the developer with SPECIFIC feedback:
  - Which criterion failed
  - What exactly is wrong (file, line number if possible)
  - What needs to change
- Do NOT approve until all blocking criteria pass

## Important
- Be specific. "The code needs improvement" is NOT acceptable feedback.
- Always check the git diff, not just the final file state.
- Run tests yourself — don't trust the developer's claim that they pass.
```

**Step 2: Commit**

```bash
git add agents/reviewer.md
git commit -m "feat: add reviewer agent definition with strict criteria"
```

### Task 8.2: Create profiler agent

**Files:**
- Create: `agents/profiler.md`

**Step 1: Write the profiler agent definition**

```markdown
---
name: profiler
description: |
  Use this agent during the gather-context phase to run exploratory PySpark queries against client data and generate a structured data profile.
model: inherit
---

You are a data profiler for a client analytics project. Your job is to thoroughly explore a dataset and produce a structured profile that informs human decision-making.

## What You Produce

Generate `docs/context/data-profile.md` with these sections:

### 1. Overview
- Row count
- Column count
- File format and size
- Date range (if applicable)

### 2. Column Inventory
For each column:
- Name, data type (as detected), nullability
- Null count and percentage
- Unique value count (cardinality)
- Sample values (first 5 distinct)

### 3. Numeric Distributions
For each numeric column:
- Min, max, mean, median, std dev
- Percentiles (25th, 50th, 75th, 95th, 99th)
- Zero count
- Outlier indicators (values beyond 3 standard deviations)

### 4. Categorical Analysis
For each categorical/string column:
- Value frequency distribution (top 20 values)
- Number of levels
- Potential grouping suggestions (levels with <1% frequency)

### 5. Data Quality Summary
- Columns with >5% nulls (flagged)
- Columns with >50% nulls (critical flag)
- Columns with single values (zero variance — candidates for dropping)
- Duplicate row count
- Potential data type mismatches (numbers stored as strings, etc.)

### 6. Correlation Preview
- Pairwise correlations for numeric columns (top 10 strongest)
- Flag any highly correlated pairs (>0.9) as potential multicollinearity

## How to Execute

- Use PySpark DataFrame API for all queries
- Use `.describe()`, `.summary()`, and custom aggregations
- Cache the DataFrame after initial load if running multiple analyses
- Print results clearly — this output becomes documentation

## Important
- Do NOT make analytical judgments about the data. You produce facts, not interpretations.
- Flag concerns (high nulls, low variance, type mismatches) but do not recommend actions.
- The human analyst decides what to do with the profile.
```

**Step 2: Commit**

```bash
git add agents/profiler.md
git commit -m "feat: add profiler agent definition for data exploration"
```

---

## Epic 9: Phase Skills

### Task 9.1: Create gather-context skill

**Files:**
- Create: `skills/gather-context/SKILL.md`

**Step 1: Write the skill**

```markdown
---
name: gather-context
description: Use when starting Phase 1 of a client project. Runs data profiling via the profiler agent and conducts analyst Q&A. Requires project-state.yaml to show current_phase as gather_context.
---

# Gather Context

## Overview

Phase 1 of the one-shot-build workflow. Profile the client data and conduct a Q&A with the analyst to understand the project.

## Pre-Conditions

- `project-state.yaml` exists with `workflow.current_phase: gather_context`
- Client data file is accessible (ask the user for the path if not known)

## Process

### Step 1: Locate the data
Use AskUserQuestion to ask: "Where is the client data file? (path to CSV/Excel/Parquet)"

### Step 2: Profile the data
Dispatch the **profiler** subagent with the Task tool:
- subagent_type: use the `profiler` agent definition
- Prompt: "Profile the data at [path]. Write results to docs/context/data-profile.md."
- Wait for the profiler to complete

### Step 3: Review the profile
Read `docs/context/data-profile.md` and present a summary to the analyst.
Highlight any data quality concerns (high nulls, low variance, type mismatches).

### Step 4: Analyst Q&A
Conduct an interactive Q&A session with the analyst. Ask ONE question at a time:
- What is the business objective for this project?
- What is the target variable?
- Are there known data quality issues?
- Are there columns that should be excluded?
- What is the expected output format?
- Any domain-specific constraints?

Save responses to `docs/context/analyst-notes.md`.

### Step 5: Gate check
Use AskUserQuestion: "Does the data profile look complete? Ready to move to epic definition?"
- If yes: update `project-state.yaml` → `workflow.current_phase: define_epics`
- If no: ask what needs further exploration

### Step 6: Commit and log progress
```bash
git add docs/context/
git commit -m "docs: add data profile and analyst notes (Phase 1 complete)"
```

Log: "Phase 1 (gather context) complete. Data profiled, analyst Q&A conducted."

Tell the user: "Context gathered. Run `/define-epics` to break the project into epics."
```

**Step 2: Commit**

```bash
git add skills/gather-context/SKILL.md
git commit -m "feat: add gather-context skill (Phase 1)"
```

### Task 9.2: Create define-epics skill

**Files:**
- Create: `skills/define-epics/SKILL.md`

**Step 1: Write the skill**

```markdown
---
name: define-epics
description: Use when Phase 1 is complete and it's time to break the project into epics. Collaboratively define epics with the analyst. Requires current_phase to be define_epics.
---

# Define Epics

## Overview

Phase 2 of the one-shot-build workflow. Collaboratively break the project into epics with the analyst.

## Pre-Conditions

- `project-state.yaml` shows `workflow.current_phase: define_epics`
- `docs/context/data-profile.md` and `docs/context/analyst-notes.md` exist

## Process

### Step 1: Read context
Read `docs/context/data-profile.md` and `docs/context/analyst-notes.md` to understand the project.

### Step 2: Propose epic breakdown
Based on the data profile and analyst notes, propose a breakdown of the project into sequential epics. Present to the analyst:

```
## Proposed Epics

1. **Data Loading & Validation** — Load client data, validate schema, apply quality thresholds
2. **Data Translation** — Column renaming, type casting, variable grouping per config
3. **[Model Name] Execution** — Fit [model] with provided config and hyperparameters
4. **Report Generation** — Produce coefficient tables, predictions, summaries
...
```

### Step 3: Refine with analyst
Ask ONE question at a time to refine:
- "Does this epic breakdown match how you see the project?"
- "Should any epics be split or combined?"
- "What's the right order?"
- "Are there epics I'm missing?"

### Step 4: Write epic specs
For each agreed epic, create a YAML file in `docs/epics/`:

```yaml
# docs/epics/01-data-loading.yaml
name: "Data Loading & Validation"
description: "Load client data files, validate against schema, apply quality thresholds"
acceptance_criteria:
  - "All specified data files loaded successfully"
  - "Schema validation passes against project-config.yaml"
  - "Data quality thresholds enforced per data-quality-thresholds.yaml"
  - "Issue log written for any quality concerns"
dependencies: []
estimated_steps: 4
```

### Step 5: Update state
- Add all epics to `project-state.yaml` under `epics:` with `status: pending`
- Set the first epic as `workflow.current_epic`
- Set `workflow.current_phase: plan`

### Step 6: Gate check
Use AskUserQuestion: "Epic breakdown is defined. Ready to start planning the first epic?"

### Step 7: Commit and log progress
```bash
git add docs/epics/ project-state.yaml
git commit -m "docs: define project epics (Phase 2 complete)"
```

Tell the user: "Epics defined. Run `/plan-epic` to create a TDD plan for the first epic."
```

**Step 2: Commit**

```bash
git add skills/define-epics/SKILL.md
git commit -m "feat: add define-epics skill (Phase 2)"
```

### Task 9.3: Create plan-epic skill

**Files:**
- Create: `skills/plan-epic/SKILL.md`

**Step 1: Write the skill**

```markdown
---
name: plan-epic
description: Use when starting Phase 3 for the current epic. Creates a TDD plan with steps, acceptance criteria, and writes tests FIRST. Tests become immutable during build.
---

# Plan Epic

## Overview

Phase 3 of the one-shot-build workflow. Create a TDD plan for the current epic and write all tests before any implementation.

## Pre-Conditions

- `project-state.yaml` shows `workflow.current_phase: plan`
- `workflow.current_epic` is set
- Epic spec exists in `docs/epics/`

## Process

### Step 1: Read the epic spec
Read the current epic's YAML from `docs/epics/`. Understand the acceptance criteria.

### Step 2: Break into steps
Break the epic into sequential steps. Each step should be:
- One focused unit of work
- Independently testable
- Has clear acceptance criteria derived from the epic

Present the step breakdown to the user for approval.

### Step 3: Write tests (TDD)
For each step, write the test file FIRST:
- Tests live in `tests/` mirroring `src/` structure
- Each test tests ONE behavior from the step's acceptance criteria
- Tests should FAIL at this point (no implementation yet)

### Step 4: Run tests to confirm they fail
Run the test suite to confirm all new tests fail as expected:
```bash
pytest tests/ -v --tb=short
```
This confirms the tests are correctly written and will catch implementation.

### Step 5: Tag the TDD baseline
Create a git tag so the test-immutability check can reference it:
```bash
git tag tdd-baseline-<epic-name>
```

### Step 6: Write the implementation plan
Create `docs/plans/<epic-name>-plan.md` with:
- Step-by-step implementation instructions
- Which files to create/modify for each step
- Expected behavior after each step
- Reference to the test that validates each step

### Step 7: Update state
- Add all steps to `project-state.yaml` under the current epic
- Set the first step as `workflow.current_step`
- Set `workflow.current_phase: build`
- Set each step's `tests_pass: false` and `review_approved: false`

### Step 8: Commit and log progress
```bash
git add tests/ docs/plans/ project-state.yaml
git commit -m "test: write TDD tests for epic <name>; plan: add implementation plan"
```

Tell the user: "Tests written and plan created. Run `/build` to start the agent team build/review loop."

## Important
- Tests written here are IMMUTABLE during the build phase.
- The developer agent cannot modify these tests. If tests need to change, the user must return to this phase.
- Write tests that are specific enough to catch correct behavior but not so brittle that correct implementations fail.
```

**Step 2: Commit**

```bash
git add skills/plan-epic/SKILL.md
git commit -m "feat: add plan-epic skill (Phase 3 - TDD planning)"
```

### Task 9.4: Create build-step skill

**Files:**
- Create: `skills/build-step/SKILL.md`

**Step 1: Write the skill**

```markdown
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
```

**Step 2: Commit**

```bash
git add skills/build-step/SKILL.md
git commit -m "feat: add build-step skill (Phase 4 - agent team build/review)"
```

### Task 9.5: Create submit-epic skill

**Files:**
- Create: `skills/submit-epic/SKILL.md`

**Step 1: Write the skill**

```markdown
---
name: submit-epic
description: Use when all steps in the current epic are built and reviewed. Runs the definition-of-done checklist and creates a PR. Requires current_phase to be submit.
---

# Submit Epic

## Overview

Phase 5 of the one-shot-build workflow. Run final quality checks and submit a PR for the completed epic.

## Pre-Conditions

- `project-state.yaml` shows `workflow.current_phase: submit`
- All steps in the current epic have `tests_pass: true` and `review_approved: true`

## Process

### Step 1: Run Definition of Done
Execute the DoD checklist:
```bash
bash <plugin_root>/hooks/definition-of-done.sh
```

If it fails, show the failures and ask the user how to proceed.

### Step 2: Run quality scan
Execute a quality scan to catch any drift:
```bash
bash <plugin_root>/hooks/quality-scan.sh
```

Flag any findings but don't block the PR.

### Step 3: Create the PR
Generate a PR using `gh pr create`:
- Title: "Epic: [epic-name]"
- Body: Summary of what was built, list of steps completed, test results, any quality scan findings
- Base branch: main (or as configured)

### Step 4: Update state
- Set `epics.<current_epic>.status: completed`
- Set `epics.<current_epic>.pr: "#<pr_number>"`
- Determine the next epic:
  - If there are more epics with `status: pending`: set it as `current_epic`, set `current_phase: plan`
  - If all epics are complete: set `current_phase: done`
- Clear `current_step`

### Step 5: Commit state and log
```bash
git add project-state.yaml claude-progress.txt
git commit -m "chore: mark epic <name> complete, advance to next"
```

### Step 6: Report
If more epics remain:
- "PR created: [URL]. Once merged, run `/plan-epic` to start the next epic."

If all epics complete:
- "All epics complete! Final PR: [URL]. Project is done pending human review."
```

**Step 2: Commit**

```bash
git add skills/submit-epic/SKILL.md
git commit -m "feat: add submit-epic skill (Phase 5 - PR + advance)"
```

---

## Epic 10: Quality Scan Skill

### Task 10.1: Implement quality-scan script

**Files:**
- Create: `hooks/quality-scan.sh`

**Step 1: Write the script**

```bash
#!/usr/bin/env bash
# hooks/quality-scan.sh
# Background quality/deviation scan
# Checks for: coding standard violations, unused imports, hand-rolled helpers,
# TODO comments, debug prints, type annotation gaps

set -euo pipefail

echo "=== Quality Scan ==="
echo ""

findings=0

# --- Check 1: TODO/FIXME comments ---
echo "Checking for TODO/FIXME comments..."
todos=$(grep -rn "TODO\|FIXME\|HACK\|XXX" src/ 2>/dev/null || true)
if [[ -n "$todos" ]]; then
    echo "  FOUND: TODO/FIXME comments"
    echo "$todos" | head -20 | sed 's/^/    /'
    findings=$((findings + 1))
else
    echo "  OK: No TODO/FIXME comments"
fi
echo ""

# --- Check 2: Debug print statements ---
echo "Checking for debug print() statements..."
prints=$(grep -rn "print(" src/ --include="*.py" 2>/dev/null | grep -v "# noqa" || true)
if [[ -n "$prints" ]]; then
    echo "  FOUND: Debug print() statements"
    echo "$prints" | head -20 | sed 's/^/    /'
    findings=$((findings + 1))
else
    echo "  OK: No debug prints"
fi
echo ""

# --- Check 3: Unused imports (basic check) ---
echo "Checking for potential unused imports..."
if command -v ruff &>/dev/null; then
    unused=$(ruff check src/ --select F401 2>/dev/null || true)
    if [[ -n "$unused" ]]; then
        echo "  FOUND: Unused imports"
        echo "$unused" | head -20 | sed 's/^/    /'
        findings=$((findings + 1))
    else
        echo "  OK: No unused imports detected"
    fi
else
    echo "  SKIP: ruff not installed (install for unused import detection)"
fi
echo ""

# --- Check 4: Missing type hints on public functions ---
echo "Checking for functions missing type hints..."
missing_hints=$(grep -rn "def [a-zA-Z_][a-zA-Z0-9_]*(.*)[^>]*:$" src/ --include="*.py" 2>/dev/null | grep -v "__" | grep -v "-> " || true)
if [[ -n "$missing_hints" ]]; then
    echo "  FOUND: Functions missing return type hints"
    echo "$missing_hints" | head -20 | sed 's/^/    /'
    findings=$((findings + 1))
else
    echo "  OK: All public functions have return type hints"
fi
echo ""

# --- Summary ---
echo "=== Scan Complete ==="
if [[ $findings -eq 0 ]]; then
    echo "No issues found."
else
    echo "$findings issue category(ies) found. Review above for details."
fi
```

**Step 2: Make executable**

```bash
chmod +x hooks/quality-scan.sh
```

**Step 3: Commit**

```bash
git add hooks/quality-scan.sh
git commit -m "feat: implement quality-scan enforcement script"
```

### Task 10.2: Create quality-scan skill

**Files:**
- Create: `skills/quality-scan/SKILL.md`

**Step 1: Write the skill**

```markdown
---
name: quality-scan
description: Use to run a background quality scan checking for coding standard deviations, unused imports, hand-rolled helpers, and other drift.
---

# Quality Scan

## Overview

Run a background quality check on the codebase. This can be invoked at any time to catch drift from coding standards.

## Process

1. Run the quality scan script: `bash <plugin_root>/hooks/quality-scan.sh`
2. Present findings to the user
3. If findings exist, offer to fix them:
   - Auto-fixable issues (unused imports, formatting) → fix and commit
   - Manual issues (TODOs, missing type hints) → list for the user to address
4. Log the scan to `claude-progress.txt`

## When to Run

- After completing an epic (before /submit)
- Periodically during long build phases
- When the user explicitly requests `/quality-scan`
```

**Step 2: Commit**

```bash
git add skills/quality-scan/SKILL.md
git commit -m "feat: add quality-scan skill for background quality checks"
```

---

## Epic 11: Remaining Commands

### Task 11.1: Create /next command

**Files:**
- Create: `commands/next.md`

**Step 1: Write the command**

```markdown
---
description: "Advance to the next step in the workflow based on current state."
disable-model-invocation: true
---

Read project-state.yaml and determine the current phase. Then invoke the appropriate one-shot-build skill:
- If current_phase is gather_context: invoke one-shot-build:gather-context
- If current_phase is define_epics: invoke one-shot-build:define-epics
- If current_phase is plan: invoke one-shot-build:plan-epic
- If current_phase is build: invoke one-shot-build:build-step
- If current_phase is submit: invoke one-shot-build:submit-epic
- If current_phase is done: tell the user all epics are complete

Follow the invoked skill exactly as presented to you.
```

**Step 2: Commit**

```bash
git add commands/next.md
git commit -m "feat: add /next command for automatic phase advancement"
```

### Task 11.2: Create review-step skill (standalone review invocation)

**Files:**
- Create: `skills/review-step/SKILL.md`

**Step 1: Write the skill**

```markdown
---
name: review-step
description: Use to manually invoke the reviewer agent on the current step's work, outside of the agent team flow.
---

# Review Step

## Overview

Manually invoke the reviewer agent to review the current step's work. This is useful when running outside the agent team flow or when the automatic review needs to be re-run.

## Process

1. Read `project-state.yaml` to identify the current epic and step
2. Get the git diff since the last approved step (or TDD baseline)
3. Dispatch the **reviewer** subagent with the Task tool:
   - Provide: the step spec, the diff, test results, review criteria
4. Process the reviewer's output:
   - If approved: update state (`review_approved: true`), log progress
   - If changes requested: present feedback to the user/developer
```

**Step 2: Commit**

```bash
git add skills/review-step/SKILL.md
git commit -m "feat: add review-step skill for manual review invocation"
```

---

## Epic 12: Integration and Polish

### Task 12.1: Add .gitignore for the plugin

**Files:**
- Create: `.gitignore`

**Step 1: Write .gitignore**

```
node_modules/
*.log
.DS_Store
Thumbs.db
```

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .gitignore for plugin repo"
```

### Task 12.2: Clean up placeholder files

**Step 1: Remove .gitkeep files from directories that now have content**

```bash
rm -f skills/.gitkeep hooks/.gitkeep commands/.gitkeep agents/.gitkeep templates/.gitkeep lib/.gitkeep
```

**Step 2: Commit**

```bash
git add -A
git commit -m "chore: remove placeholder .gitkeep files"
```

### Task 12.3: Run full test suite

**Step 1: Run all BATS tests**

```bash
npx bats tests/*.bats
```

Expected: All tests PASS

### Task 12.4: Update README.md

**Files:**
- Modify: `README.md`

**Step 1: Update README with installation and usage instructions**

Add sections for:
- Installation (how to install the plugin)
- Quick Start (how to use `/init`, `/status`, `/next`)
- Workflow overview
- Link to design doc

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README with plugin installation and usage"
```

---

## Epic 13: Agent Debrief Protocol

### Task 13.1: Write failing tests for debrief validation

**Files:**
- Create: `tests/debrief_test.bats`

**Step 1: Write tests**

```bash
#!/usr/bin/env bats
# tests/debrief_test.bats

setup() {
    load 'node_modules/bats-support/load'
    load 'node_modules/bats-assert/load'

    TEST_DIR="$(mktemp -d)"
    export PROJECT_ROOT="$TEST_DIR"

    SCRIPT="${BATS_TEST_DIRNAME}/../hooks/check-debrief.sh"

    mkdir -p "$TEST_DIR/docs/context"
}

teardown() {
    rm -rf "$TEST_DIR"
}

@test "fails when no debrief log exists" {
    run bash "$SCRIPT" "step-01" "01-data-loading"
    assert_failure
    assert_output --partial "No debrief entry"
}

@test "fails when debrief log exists but has no entry for the step" {
    cat > "$TEST_DIR/docs/context/debrief-log.yaml" <<'YAML'
- step: "step-02"
  epic: "01-data-loading"
  agent: "developer"
  what_worked:
    - "Something worked"
YAML
    run bash "$SCRIPT" "step-01" "01-data-loading"
    assert_failure
    assert_output --partial "No debrief entry"
}

@test "passes when debrief entry exists for the step" {
    cat > "$TEST_DIR/docs/context/debrief-log.yaml" <<'YAML'
- step: "step-01"
  epic: "01-data-loading"
  agent: "developer"
  what_worked:
    - "Data loaded successfully"
  discoveries:
    - "File has 5000 rows"
YAML
    run bash "$SCRIPT" "step-01" "01-data-loading"
    assert_success
    assert_output --partial "PASS"
}
```

**Step 2: Run tests to verify they fail**

Run: `npx bats tests/debrief_test.bats`
Expected: FAIL

**Step 3: Commit**

```bash
git add tests/debrief_test.bats
git commit -m "test: add failing tests for debrief validation"
```

### Task 13.2: Implement debrief check script

**Files:**
- Create: `hooks/check-debrief.sh`

**Step 1: Write the script**

```bash
#!/usr/bin/env bash
# hooks/check-debrief.sh
# Validates that a debrief entry exists for a given step.
# Usage: check-debrief.sh <step-name> <epic-name>
# Exit 0 = PASS, Exit 1 = FAIL

set -euo pipefail

STEP="${1:?Usage: check-debrief.sh <step-name> <epic-name>}"
EPIC="${2:?Usage: check-debrief.sh <step-name> <epic-name>}"

PROJECT_ROOT="${PROJECT_ROOT:-$(pwd)}"
DEBRIEF_FILE="${PROJECT_ROOT}/docs/context/debrief-log.yaml"

if [[ ! -f "$DEBRIEF_FILE" ]]; then
    echo "FAIL: No debrief entry found for ${STEP} (${EPIC})"
    echo "  debrief-log.yaml does not exist."
    echo "  The developer must write a debrief before marking the step complete."
    exit 1
fi

# Check if there's an entry matching both step and epic
if command -v yq &>/dev/null; then
    match=$(yq eval "[.[] | select(.step == \"${STEP}\" and .epic == \"${EPIC}\")] | length" "$DEBRIEF_FILE" 2>/dev/null || echo "0")
else
    # Fallback: grep-based check
    match=$(grep -c "step: \"${STEP}\"" "$DEBRIEF_FILE" 2>/dev/null || echo "0")
fi

if [[ "$match" -gt 0 ]]; then
    echo "PASS: Debrief entry found for ${STEP} (${EPIC})"
    exit 0
else
    echo "FAIL: No debrief entry found for ${STEP} (${EPIC})"
    echo "  The developer must write a debrief before marking the step complete."
    echo ""
    echo "  Required debrief fields: what_worked, what_failed, discoveries, decisions"
    exit 1
fi
```

**Step 2: Make executable**

```bash
chmod +x hooks/check-debrief.sh
```

**Step 3: Run tests to verify they pass**

Run: `npx bats tests/debrief_test.bats`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add hooks/check-debrief.sh
git commit -m "feat: implement debrief validation enforcement script"
```

### Task 13.3: Update session-start hook to inject learnings

**Files:**
- Modify: `hooks/session-start.sh`

**Step 1: Add debrief summary injection**

After the existing state context building, add logic to read the last 5 debrief entries from `docs/context/debrief-log.yaml` and include a summary in the injected context.

Add these lines after the phase-based next-action section:

```bash
# Include recent learnings from debrief log
DEBRIEF_FILE="${PROJECT_ROOT}/docs/context/debrief-log.yaml"
if [[ -f "$DEBRIEF_FILE" ]] && command -v yq &>/dev/null; then
    recent_discoveries=$(yq eval '[.[-5:][].discoveries // []] | flatten | .[]' "$DEBRIEF_FILE" 2>/dev/null | head -10 || echo "")
    if [[ -n "$recent_discoveries" ]]; then
        context+="\\n\\n## Recent Learnings\\n"
        while IFS= read -r discovery; do
            context+="- ${discovery}\\n"
        done <<< "$recent_discoveries"
    fi
fi
```

**Step 2: Run session-start tests to verify no regression**

Run: `npx bats tests/session_start_test.bats`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add hooks/session-start.sh
git commit -m "feat: inject recent debrief learnings into session-start context"
```

### Task 13.4: Update build-step skill to require debriefs

**Files:**
- Modify: `skills/build-step/SKILL.md`

**Step 1: Add debrief instructions to developer and reviewer prompts**

In the developer teammate instructions section, add:

```
- After completing each step, write a debrief entry to docs/context/debrief-log.yaml:
  - what_worked: approaches that succeeded
  - what_failed: approaches tried and why they didn't work
  - discoveries: facts learned about the data, APIs, or system
  - decisions: choices made and their reasoning
- The TaskCompleted hook will block completion if no debrief entry exists
```

In the reviewer teammate instructions section, add:

```
- After reviewing, append your own debrief entry with:
  - review_notes: what you found during review
  - patterns_to_watch: recurring issues to watch for in future steps
```

**Step 2: Commit**

```bash
git add skills/build-step/SKILL.md
git commit -m "feat: add debrief requirement to build-step skill"
```

---

## Summary

| Epic | Tasks | Description |
|------|-------|-------------|
| 1 | 1.1-1.2 | Plugin manifest and directory structure |
| 2 | 2.1-2.2 | State library with BATS tests (TDD) |
| 3 | 3.1-3.4 | All project scaffolding templates |
| 4 | 4.1-4.2 | Init skill + /init command |
| 5 | 5.1-5.3 | Session start hook with tests (TDD) |
| 6 | 6.1-6.2 | Status skill + /status command |
| 7 | 7.1-7.4 | Enforcement scripts with tests (TDD) |
| 8 | 8.1-8.2 | Reviewer and profiler agent definitions |
| 9 | 9.1-9.5 | All phase skills (gather-context through submit) |
| 10 | 10.1-10.2 | Quality scan script + skill |
| 11 | 11.1-11.2 | Remaining commands (/next, review-step) |
| 12 | 12.1-12.4 | Integration, cleanup, test run, README |
| 13 | 13.1-13.4 | Agent debrief protocol with tests (TDD) |

**Total: 13 epics, 29 tasks**
