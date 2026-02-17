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

## Epic 13: Compound Learning System — Solution Docs + Schema

### Task 13.1: Create solution document schema and templates

**Files:**
- Create: `templates/solution-doc.md.template`
- Create: `lib/solution-schema.yaml`

**Step 1: Write the solution document template**

```markdown
---
title: "{{TITLE}}"
date: {{DATE}}
problem_type:       # enum: data_quality_issue, runtime_error, performance_issue, config_error, integration_issue, test_failure
component:          # enum: data_loading, data_translation, model_execution, reporting, pipeline, testing, infrastructure
severity:           # enum: critical, high, medium, low
root_cause:         # enum: missing_validation, type_mismatch, memory_overflow, null_handling, config_mismatch, api_misuse, race_condition, schema_drift
resolution_type:    # enum: code_fix, config_change, workaround, documentation, dependency_update

applies_to:
  scope:            # universal | conditional
  project_types: [] # e.g., [churn_modeling, pricing, segmentation]
  data_characteristics: [] # e.g., [large_dataset, sparse_nulls, categorical_heavy]
  tools: []         # e.g., [pyspark, databricks, custom_model_library]

# Lifecycle metadata (for pruning)
status: active      # active | deprecated | superseded
superseded_by: ""   # path to replacement doc (if superseded)
last_validated: {{DATE}}  # last date confirmed still applicable
context:
  library_versions: {}  # e.g., { custom_model_library: ">=2.1" }
  tool_versions: {}     # e.g., { pyspark: ">=3.4" }

tags: []
---

## Problem
[What happened]

## Symptoms
[Observable indicators]

## What Didn't Work
[Approaches tried and why they failed]

## Solution
[What fixed it, with code before/after]

## Why This Works
[Root cause explanation]

## Prevention
[How to avoid this in future]
```

**Step 2: Write the schema validation file**

`lib/solution-schema.yaml` defines valid enum values for frontmatter validation:

```yaml
# lib/solution-schema.yaml — Valid values for solution doc frontmatter
# Used by validate-solution-doc.sh to enforce schema

problem_type:
  - data_quality_issue
  - runtime_error
  - performance_issue
  - config_error
  - integration_issue
  - test_failure

component:
  - data_loading
  - data_translation
  - model_execution
  - reporting
  - pipeline
  - testing
  - infrastructure

severity:
  - critical
  - high
  - medium
  - low

root_cause:
  - missing_validation
  - type_mismatch
  - memory_overflow
  - null_handling
  - config_mismatch
  - api_misuse
  - race_condition
  - schema_drift

resolution_type:
  - code_fix
  - config_change
  - workaround
  - documentation
  - dependency_update

scope:
  - universal
  - conditional

status:
  - active
  - deprecated
  - superseded
```

**Step 3: Commit**

```bash
git add templates/solution-doc.md.template lib/solution-schema.yaml
git commit -m "feat: add solution document template and schema with enum validation"
```

### Task 13.2: Write failing tests for solution doc validation

**Files:**
- Create: `tests/validate_solution_doc_test.bats`

**Step 1: Write tests**

```bash
#!/usr/bin/env bats
# tests/validate_solution_doc_test.bats

setup() {
    load 'node_modules/bats-support/load'
    load 'node_modules/bats-assert/load'

    TEST_DIR="$(mktemp -d)"
    SCRIPT="${BATS_TEST_DIRNAME}/../hooks/validate-solution-doc.sh"
    SCHEMA="${BATS_TEST_DIRNAME}/../lib/solution-schema.yaml"
}

teardown() {
    rm -rf "$TEST_DIR"
}

@test "passes for a valid solution doc" {
    cat > "$TEST_DIR/valid-doc.md" <<'EOF'
---
title: "Null handling in target column"
date: 2026-03-10
problem_type: runtime_error
component: model_execution
severity: critical
root_cause: null_handling
resolution_type: code_fix
applies_to:
  scope: universal
  project_types: []
  data_characteristics: []
  tools: [custom_model_library]
tags: [null-handling]
---

## Problem
Model library crashes on null target.

## Solution
Add null check before calling library.
EOF

    run bash "$SCRIPT" "$TEST_DIR/valid-doc.md" "$SCHEMA"
    assert_success
    assert_output --partial "PASS"
}

@test "fails when problem_type has invalid enum value" {
    cat > "$TEST_DIR/invalid-doc.md" <<'EOF'
---
title: "Test doc"
date: 2026-03-10
problem_type: banana
component: model_execution
severity: critical
root_cause: null_handling
resolution_type: code_fix
applies_to:
  scope: universal
  project_types: []
  data_characteristics: []
  tools: []
tags: []
---

## Problem
Test.
EOF

    run bash "$SCRIPT" "$TEST_DIR/invalid-doc.md" "$SCHEMA"
    assert_failure
    assert_output --partial "problem_type"
}

@test "fails when required frontmatter fields are missing" {
    cat > "$TEST_DIR/missing-fields.md" <<'EOF'
---
title: "Test doc"
date: 2026-03-10
---

## Problem
Test.
EOF

    run bash "$SCRIPT" "$TEST_DIR/missing-fields.md" "$SCHEMA"
    assert_failure
    assert_output --partial "missing"
}

@test "fails when status has invalid enum value" {
    cat > "$TEST_DIR/bad-status.md" <<'EOF'
---
title: "Test doc"
date: 2026-03-10
problem_type: runtime_error
component: model_execution
severity: critical
root_cause: null_handling
resolution_type: code_fix
status: banana
applies_to:
  scope: universal
  project_types: []
  data_characteristics: []
  tools: []
tags: []
---

## Problem
Test.
EOF

    run bash "$SCRIPT" "$TEST_DIR/bad-status.md" "$SCHEMA"
    assert_failure
    assert_output --partial "status"
}

@test "detects contradiction with existing doc (same component+problem_type+root_cause)" {
    mkdir -p "$TEST_DIR/docs/solutions/model-library-issues"
    cat > "$TEST_DIR/docs/solutions/model-library-issues/old-doc.md" <<'EOF'
---
title: "Old null handling fix"
date: 2026-02-01
problem_type: runtime_error
component: model_execution
root_cause: null_handling
severity: high
resolution_type: workaround
status: active
applies_to:
  scope: universal
  project_types: []
  data_characteristics: []
  tools: []
tags: []
---

## Problem
Old workaround.
EOF

    cat > "$TEST_DIR/new-doc.md" <<'EOF'
---
title: "Better null handling fix"
date: 2026-03-10
problem_type: runtime_error
component: model_execution
root_cause: null_handling
severity: critical
resolution_type: code_fix
status: active
applies_to:
  scope: universal
  project_types: []
  data_characteristics: []
  tools: []
tags: []
---

## Problem
Better fix.
EOF

    run bash "$SCRIPT" "$TEST_DIR/new-doc.md" "$SCHEMA" "$TEST_DIR/docs/solutions"
    assert_success
    # Should pass validation but warn about overlap
    assert_output --partial "OVERLAP"
}
```

**Step 2: Run tests to verify they fail**

Run: `npx bats tests/validate_solution_doc_test.bats`
Expected: FAIL (script does not exist yet)

**Step 3: Commit**

```bash
git add tests/validate_solution_doc_test.bats
git commit -m "test: add failing tests for solution doc validation"
```

### Task 13.3: Implement solution doc validation script

**Files:**
- Create: `hooks/validate-solution-doc.sh`

**Step 1: Write the script**

```bash
#!/usr/bin/env bash
# hooks/validate-solution-doc.sh
# Validates a solution document's YAML frontmatter against the schema.
# Also checks for contradictions with existing docs (same component+problem_type+root_cause).
# Usage: validate-solution-doc.sh <doc-path> [schema-path] [solutions-dir]
# Exit 0 = PASS (may include OVERLAP warnings), Exit 1 = FAIL

set -euo pipefail

DOC_PATH="${1:?Usage: validate-solution-doc.sh <doc-path> [schema-path] [solutions-dir]}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
SCHEMA_PATH="${2:-${SCRIPT_DIR}/../lib/solution-schema.yaml}"
SOLUTIONS_DIR="${3:-}"  # Optional: path to docs/solutions/ for contradiction detection

if [[ ! -f "$DOC_PATH" ]]; then
    echo "FAIL: File not found: $DOC_PATH"
    exit 1
fi

if ! command -v yq &>/dev/null; then
    echo "FAIL: yq is required for solution doc validation"
    exit 1
fi

failures=()
warnings=()

# Extract frontmatter (between --- markers)
frontmatter=$(sed -n '/^---$/,/^---$/p' "$DOC_PATH" | sed '1d;$d')
if [[ -z "$frontmatter" ]]; then
    echo "FAIL: No YAML frontmatter found in $DOC_PATH"
    exit 1
fi

# Write frontmatter to temp file for yq parsing
tmp_fm=$(mktemp)
echo "$frontmatter" > "$tmp_fm"

# Check required fields
required_fields=("title" "date" "problem_type" "component" "severity" "root_cause" "resolution_type")
for field in "${required_fields[@]}"; do
    val=$(yq eval ".${field}" "$tmp_fm" 2>/dev/null)
    if [[ -z "$val" || "$val" == "null" ]]; then
        failures+=("Required field missing: ${field}")
    fi
done

# Validate enum fields against schema
enum_fields=("problem_type" "component" "severity" "root_cause" "resolution_type" "status")
for field in "${enum_fields[@]}"; do
    val=$(yq eval ".${field}" "$tmp_fm" 2>/dev/null)
    if [[ -n "$val" && "$val" != "null" ]]; then
        match=$(yq eval ".${field}[] | select(. == \"${val}\")" "$SCHEMA_PATH" 2>/dev/null)
        if [[ -z "$match" ]]; then
            failures+=("Invalid ${field}: '${val}' — see lib/solution-schema.yaml for valid values")
        fi
    fi
done

# Validate applies_to.scope
scope=$(yq eval ".applies_to.scope" "$tmp_fm" 2>/dev/null)
if [[ -n "$scope" && "$scope" != "null" ]]; then
    match=$(yq eval ".scope[] | select(. == \"${scope}\")" "$SCHEMA_PATH" 2>/dev/null)
    if [[ -z "$match" ]]; then
        failures+=("Invalid applies_to.scope: '${scope}' — must be 'universal' or 'conditional'")
    fi
fi

# --- Contradiction detection ---
# Check for existing active docs with the same component+problem_type+root_cause
if [[ -n "$SOLUTIONS_DIR" && -d "$SOLUTIONS_DIR" ]]; then
    new_component=$(yq eval ".component" "$tmp_fm" 2>/dev/null)
    new_problem=$(yq eval ".problem_type" "$tmp_fm" 2>/dev/null)
    new_root=$(yq eval ".root_cause" "$tmp_fm" 2>/dev/null)

    if [[ -n "$new_component" && -n "$new_problem" && -n "$new_root" ]]; then
        # Search existing docs for matching combination
        while IFS= read -r existing_doc; do
            [[ "$existing_doc" == "$DOC_PATH" ]] && continue
            [[ "$existing_doc" == *"_archived"* ]] && continue

            ex_fm=$(sed -n '/^---$/,/^---$/p' "$existing_doc" | sed '1d;$d')
            tmp_ex=$(mktemp)
            echo "$ex_fm" > "$tmp_ex"

            ex_component=$(yq eval ".component" "$tmp_ex" 2>/dev/null)
            ex_problem=$(yq eval ".problem_type" "$tmp_ex" 2>/dev/null)
            ex_root=$(yq eval ".root_cause" "$tmp_ex" 2>/dev/null)
            ex_status=$(yq eval ".status" "$tmp_ex" 2>/dev/null)
            ex_title=$(yq eval ".title" "$tmp_ex" 2>/dev/null)

            rm -f "$tmp_ex"

            if [[ "$ex_component" == "$new_component" && \
                  "$ex_problem" == "$new_problem" && \
                  "$ex_root" == "$new_root" && \
                  "$ex_status" == "active" ]]; then
                warnings+=("OVERLAP: Existing active doc covers same component+problem_type+root_cause: ${existing_doc} (\"${ex_title}\"). Consider marking it as superseded.")
            fi
        done < <(find "$SOLUTIONS_DIR" -name "*.md" -not -path "*/_archived/*" 2>/dev/null)
    fi
fi

rm -f "$tmp_fm"

# Report
if [[ ${#failures[@]} -gt 0 ]]; then
    echo "FAIL: Solution doc validation failed: $(basename "$DOC_PATH")"
    echo ""
    for fail in "${failures[@]}"; do
        echo "  - $fail"
    done
    exit 1
fi

# Warnings (non-blocking)
for warn in "${warnings[@]}"; do
    echo "  $warn"
done

echo "PASS: Solution doc validates against schema: $(basename "$DOC_PATH")"
exit 0
```

**Step 2: Make executable**

```bash
chmod +x hooks/validate-solution-doc.sh
```

**Step 3: Run tests to verify they pass**

Run: `npx bats tests/validate_solution_doc_test.bats`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add hooks/validate-solution-doc.sh
git commit -m "feat: implement solution doc validation against YAML schema"
```

### Task 13.4: Update init skill to scaffold solution directories

**Files:**
- Modify: `skills/harness-init/SKILL.md`

**Step 1: Add solution doc directories to the scaffold**

In the "Directory Structure to Create" section, add:

```
├── docs/
│   ├── solutions/                    # Per-project solution docs (compound learning)
│   │   ├── data-quality-issues/
│   │   ├── model-library-issues/
│   │   ├── pyspark-issues/
│   │   ├── performance-issues/
│   │   ├── integration-issues/
│   │   ├── best-practices/
│   │   └── patterns/
│   │       └── critical-patterns.md  # Always-read required knowledge
```

In the "After Scaffolding" section, create a seed `critical-patterns.md`:

```markdown
# Critical Patterns

> This file is ALWAYS read by the learnings-researcher agent. Add patterns here
> that every developer/agent must know about for this project.

<!-- Add critical patterns as they are discovered -->
```

**Step 2: Commit**

```bash
git add skills/harness-init/SKILL.md
git commit -m "feat: add solution doc directory structure to init scaffold"
```

---

## Epic 14: Learnings Researcher Agent + Knowledge Retrieval

### Task 14.1: Create learnings-researcher agent definition

**Files:**
- Create: `agents/learnings-researcher.md`

**Step 1: Write the agent definition**

```markdown
---
name: learnings-researcher
description: |
  Use this agent to search for relevant prior solutions before planning or building. Searches both per-project docs/solutions/ and the shared team-knowledge repo using a grep-first filtering strategy with project profile matching.
model: inherit
---

You are a knowledge researcher for a client analytics project. Your job is to find relevant prior solutions that can prevent known problems and accelerate development.

## When You Are Invoked

- During `/plan-epic` — before the developer writes tests
- During `/build` — when the developer encounters a problem
- You are a subagent; return a distilled summary, not raw file contents

## Search Strategy

### 1. ALWAYS read critical patterns (both tiers)

```
docs/solutions/patterns/critical-patterns.md          # Project-level
<shared_knowledge_path>/docs/solutions/patterns/critical-patterns.md  # Team-level
```

### 2. Read the project profile

Read `.harnessrc` to get `project_profile` (project_types, data_characteristics, tools, etc.)

### 3. Filter by lifecycle status and version compatibility

For each solution doc in both tiers, read only the YAML frontmatter (first ~30 lines).

**Skip immediately if:**
- `status` is `deprecated` or `superseded`
- `context.library_versions` or `context.tool_versions` don't match the current project's versions (check against `.harnessrc` project profile)

**Flag as potentially stale if:**
- `last_validated` is older than 90 days (configurable via `.harnessrc`)
- Surface these with a warning: "This solution may be outdated (last validated: [date])"

### 4. Filter by project profile match

Within the remaining active, version-compatible docs:
Include the doc if ANY of these overlap:
- `applies_to.project_types` overlaps with profile `project_types`
- `applies_to.data_characteristics` overlaps with profile `data_characteristics`
- `applies_to.tools` overlaps with profile `tools`
- `applies_to.scope` is `universal`

Skip docs where NO dimension overlaps.

### 5. Keyword search within filtered set

Search remaining docs for keywords related to the current task:
- Epic name, step name, component being built
- Error messages (if invoked during a failure)
- Technology names (pyspark, model library, etc.)

### 6. Full read only relevant matches

Read the full content of docs that pass both profile AND keyword filters.

### 7. Return distilled summary

Return a summary structured as:

```
## Relevant Prior Solutions

### Critical Patterns
- [pattern 1 from critical-patterns.md]
- [pattern 2]

### Directly Relevant Solutions
- **[title]** (from: project/team) — [1-sentence summary of the fix]
  - Key insight: [what to do differently]

### Possibly Relevant
- **[title]** — [why it might apply]

### Recommendations
- [specific action items for the current task based on learnings]
```

## Important

- Be concise. The developer needs actionable insights, not a research paper.
- If you find nothing relevant, say so — don't fabricate connections.
- Prefer solutions from the same component/problem_type as the current task.
- The shared knowledge path is in `.harnessrc` under `shared_knowledge_path`.
```

**Step 2: Commit**

```bash
git add agents/learnings-researcher.md
git commit -m "feat: add learnings-researcher agent for pull-based knowledge retrieval"
```

### Task 14.2: Update plan-epic skill to invoke learnings researcher

**Files:**
- Modify: `skills/plan-epic/SKILL.md`

**Step 1: Add learnings research step**

After "Step 1: Read the epic spec" and before "Step 2: Break into steps", insert:

```markdown
### Step 1.5: Search for relevant prior solutions

Dispatch the **learnings-researcher** subagent with the Task tool:
- Provide: the epic name, component type, list of step names
- Wait for the researcher to return relevant learnings
- Incorporate any critical patterns or known pitfalls into the step breakdown and test design
- If the researcher found solutions for similar problems, reference them in the implementation plan
```

**Step 2: Commit**

```bash
git add skills/plan-epic/SKILL.md
git commit -m "feat: invoke learnings-researcher during epic planning"
```

### Task 14.3: Update build-step skill for compound learning

**Files:**
- Modify: `skills/build-step/SKILL.md`

**Step 1: Add knowledge search on failure + solution doc capture**

In the developer teammate instructions, replace the old debrief requirement with:

```
Knowledge capture:
- When you resolve a notable problem (test failure fixed, workaround found, unexpected behavior):
  1. Write a solution doc to docs/solutions/<category>/ using the template
  2. Include validated YAML frontmatter (the TaskCompleted hook validates the schema)
  3. Use descriptive filenames: YYYY-MM-DD-brief-description.md

- When you encounter a problem you can't immediately solve:
  1. Ask the lead to dispatch the learnings-researcher agent
  2. The researcher will search prior solutions for similar issues
  3. Apply any relevant findings before continuing

- At epic boundaries, you'll be asked: "Is this project-specific or team-wide?"
  - Project-specific → stays in ./docs/solutions/
  - Team-wide → will be copied to the shared knowledge repo
```

In the reviewer teammate instructions, add:

```
- Verify any new solution docs have valid YAML frontmatter (run validate-solution-doc.sh)
- Flag solution docs that seem universally applicable (not just project-specific)
```

**Step 2: Commit**

```bash
git add skills/build-step/SKILL.md
git commit -m "feat: add compound learning (solution capture + knowledge search) to build-step"
```

### Task 14.4: Create .harnessrc template with project profile

**Files:**
- Modify: `templates/.harnessrc.template`

**Step 1: Add project profile and shared knowledge path**

Add to the existing `.harnessrc.template`:

```yaml
# Project profile for relevance matching with cross-project learnings
# The learnings-researcher agent uses this to filter solution docs
# project_profile:
#   project_types: [churn_modeling]     # What kind of project this is
#   data_characteristics: [large_dataset, sparse_nulls, categorical_heavy]
#   model_types: [logistic_regression, gradient_boosting]
#   industry: insurance
#   tools: [pyspark, databricks, custom_model_library]

# Path to the shared team knowledge repository
# shared_knowledge_path: "~/repos/team-knowledge"
```

**Step 2: Commit**

```bash
git add templates/.harnessrc.template
git commit -m "feat: add project profile and shared knowledge path to .harnessrc template"
```

### Task 14.5: Update submit-epic skill for knowledge promotion

**Files:**
- Modify: `skills/submit-epic/SKILL.md`

**Step 1: Add knowledge promotion step**

After the quality scan step and before creating the PR, add:

```markdown
### Step 2.5: Promote cross-project learnings

Review `docs/solutions/` for solution docs created during this epic.

For each doc where `applies_to.scope` is `universal` or the content is clearly not project-specific:

1. Present to the user: "These solutions from this epic might help future projects:"
   - [title] → [category/filename]

2. If the user approves promotion and `shared_knowledge_path` is configured in `.harnessrc`:
   - Copy the solution doc to `<shared_knowledge_path>/docs/solutions/<category>/`
   - Commit to the shared repo
   - Create a PR (or push directly if configured)

3. If no shared knowledge path is configured, suggest the user set one up.
```

**Step 2: Commit**

```bash
git add skills/submit-epic/SKILL.md
git commit -m "feat: add solution doc promotion to shared team knowledge repo"
```

---

## Epic 15: Self-Verification CLI + Final Wiring

### Task 15.1: Create self-check script

**Files:**
- Create: `hooks/self-check.sh`

**Step 1: Write the script**

A wrapper that runs all verification checks that the developer should run before marking a step complete:

```bash
#!/usr/bin/env bash
# hooks/self-check.sh
# Runs all pre-completion checks. Intended to be called by the developer
# agent before marking a task complete, as a self-verification step.
# Usage: self-check.sh <step-name> <epic-name> [tdd-baseline-ref]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

STEP="${1:?Usage: self-check.sh <step-name> <epic-name> [tdd-baseline-ref]}"
EPIC="${2:?Usage: self-check.sh <step-name> <epic-name> [tdd-baseline-ref]}"
BASELINE="${3:-tdd-baseline}"

echo "=== Self-Verification Check ==="
echo "Step: $STEP | Epic: $EPIC"
echo ""

passed=0
failed=0

# Check 1: Tests pass
echo "--- Running tests ---"
if pytest tests/ -v --tb=short 2>&1; then
    echo "  PASS: Tests"
    passed=$((passed + 1))
else
    echo "  FAIL: Tests"
    failed=$((failed + 1))
fi
echo ""

# Check 2: Test immutability
echo "--- Checking test immutability ---"
if bash "${SCRIPT_DIR}/check-test-immutability.sh" "$BASELINE" 2>&1; then
    passed=$((passed + 1))
else
    failed=$((failed + 1))
fi
echo ""

# Check 3: Validate any new solution docs
echo "--- Validating solution docs ---"
SCHEMA="${SCRIPT_DIR}/../lib/solution-schema.yaml"
new_docs=$(git diff --name-only --diff-filter=A HEAD -- 'docs/solutions/*.md' 'docs/solutions/**/*.md' 2>/dev/null || true)
if [[ -n "$new_docs" ]]; then
    doc_pass=true
    while IFS= read -r doc; do
        if ! bash "${SCRIPT_DIR}/validate-solution-doc.sh" "$doc" "$SCHEMA" 2>&1; then
            doc_pass=false
        fi
    done <<< "$new_docs"
    if [[ "$doc_pass" == "true" ]]; then
        echo "  PASS: All solution docs valid"
        passed=$((passed + 1))
    else
        failed=$((failed + 1))
    fi
else
    echo "  SKIP: No new solution docs"
    passed=$((passed + 1))
fi
echo ""

# Check 4: No uncommitted changes
echo "--- Checking git status ---"
if [[ -z "$(git status --porcelain 2>/dev/null)" ]]; then
    echo "  PASS: All changes committed"
    passed=$((passed + 1))
else
    echo "  FAIL: Uncommitted changes detected"
    failed=$((failed + 1))
fi
echo ""

# Summary
echo "=== Self-Check Complete ==="
echo "$passed passed, $failed failed"

if [[ $failed -gt 0 ]]; then
    echo "Fix the above issues before marking the step complete."
    exit 1
else
    echo "All checks pass. Safe to mark step as complete."
    exit 0
fi
```

**Step 2: Make executable**

```bash
chmod +x hooks/self-check.sh
```

**Step 3: Update developer prompt in build-step skill**

In the developer teammate instructions, add:

```
- Before marking a step complete, run self-verification:
  bash <plugin_root>/hooks/self-check.sh <step-name> <epic-name> tdd-baseline-<epic>
- Fix any failures before proceeding. Do NOT rely on the TaskCompleted hook to catch these.
```

**Step 4: Commit**

```bash
git add hooks/self-check.sh skills/build-step/SKILL.md
git commit -m "feat: add self-check verification script with solution doc validation"
```

### Task 15.2: Update hooks.json with all hook events

**Files:**
- Modify: `hooks/hooks.json`

**Step 1: Add TaskCompleted hook for enforcement**

Update `hooks/hooks.json` to include all configured hooks:

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

Note: `TaskCompleted` and `TeammateIdle` hooks depend on Claude Code's agent teams API finalization. The enforcement scripts (`check-test-immutability.sh`, `validate-solution-doc.sh`, `definition-of-done.sh`) are all callable via the self-check CLI pattern in the meantime.

**Step 2: Commit**

```bash
git add hooks/hooks.json
git commit -m "feat: finalize hooks.json configuration"
```

---

## Epic 16: Knowledge Pruning (`/prune-knowledge`)

### Task 16.1: Create prune-knowledge skill

**Files:**
- Create: `skills/prune-knowledge/SKILL.md`

**Step 1: Write the skill**

```markdown
---
name: prune-knowledge
description: Use periodically to review and clean up solution docs. Identifies stale, deprecated, superseded, and duplicate solutions across both project-level and team-level knowledge stores. Non-destructive — archives rather than deletes.
---

# Prune Knowledge

## Overview

Review all solution docs for staleness, contradictions, and low-value entries. Surface candidates to the human for review. Archive deprecated docs. This should be run periodically (e.g., at the start of a new project or quarterly).

## Process

### Step 1: Scan both tiers

Read `.harnessrc` for `shared_knowledge_path`. Scan:
- `docs/solutions/` (project-level)
- `<shared_knowledge_path>/docs/solutions/` (team-level, if configured)

For each solution doc, extract YAML frontmatter.

### Step 2: Auto-archive superseded docs

Find docs where `status: superseded` and `superseded_by` is filled.
Move them to `<category>/_archived/` subdirectory.

Report: "Archived N superseded docs."

### Step 3: Flag stale docs

Find active docs where `last_validated` is older than the staleness threshold
(default: 90 days, configurable via `.harnessrc` under `pruning.staleness_threshold_days`).

Present to the user as a checklist:

```
## Potentially Stale Solutions (last validated > 90 days ago)

- [ ] **Null handling in target column** (last validated: 2026-01-15)
      docs/solutions/model-library-issues/2026-01-15-null-target.md
      Action: [Still valid → refresh date] [Outdated → deprecate] [Skip]

- [ ] **PySpark broadcast join OOM** (last validated: 2025-11-20)
      docs/solutions/pyspark-issues/2025-11-20-broadcast-oom.md
      Action: [Still valid → refresh date] [Outdated → deprecate] [Skip]
```

For each:
- "Still valid" → update `last_validated` to today
- "Outdated" → set `status: deprecated`, move to `_archived/`
- "Skip" → leave as-is for next review

### Step 4: Check version compatibility

Find active docs with `context.library_versions` or `context.tool_versions` constraints.
Compare against the current project's `.harnessrc` profile.

Flag docs where version constraints are incompatible with the current project:

```
## Version-Incompatible Solutions

- **PySpark 3.2 shuffle fix** — requires pyspark: ">=3.2, <3.4", current project uses 3.5
  Action: [Deprecate] [Update version range] [Skip]
```

### Step 5: Detect duplicates

Find docs with the same `component` + `problem_type` + `root_cause` combination that are both `status: active`.

Present for merge or supersession:

```
## Duplicate Solutions (same component + problem_type + root_cause)

Group 1: model_execution / runtime_error / null_handling
  - 2026-01-15-null-target-workaround.md (workaround)
  - 2026-03-10-null-target-fix.md (code_fix)
  Action: [Merge into one] [Mark older as superseded] [Keep both] [Skip]
```

### Step 6: Summary report

```
## Pruning Summary

- Archived: N superseded docs
- Refreshed: N docs (last_validated updated)
- Deprecated: N stale/outdated docs
- Flagged for review: N version-incompatible docs
- Duplicate groups found: N
- Total active docs remaining: N (project) + N (team)
```

### Step 7: Commit changes

```bash
git add docs/solutions/
git commit -m "chore: prune knowledge base — archive N, refresh N, deprecate N"
```

If team-level docs were modified:
```bash
cd <shared_knowledge_path>
git add docs/solutions/
git commit -m "chore: prune team knowledge — archive N, refresh N, deprecate N"
```

## Configuration

```yaml
# .harnessrc
pruning:
  staleness_threshold_days: 90     # flag docs older than this
  auto_archive_superseded: true    # auto-archive without asking
```
```

**Step 2: Commit**

```bash
git add skills/prune-knowledge/SKILL.md
git commit -m "feat: add prune-knowledge skill for periodic knowledge base cleanup"
```

### Task 16.2: Create /prune-knowledge command

**Files:**
- Create: `commands/prune-knowledge.md`

**Step 1: Write the command**

```markdown
---
description: "Review and clean up solution docs. Archives stale/superseded docs, flags duplicates."
disable-model-invocation: true
---

Invoke the one-shot-build:prune-knowledge skill and follow it exactly as presented to you
```

**Step 2: Commit**

```bash
git add commands/prune-knowledge.md
git commit -m "feat: add /prune-knowledge command shorthand"
```

### Task 16.3: Update init skill to scaffold _archived directories

**Files:**
- Modify: `skills/harness-init/SKILL.md`

**Step 1: Add _archived subdirectories to the solution doc scaffold**

In the "Directory Structure to Create" section, add `_archived/` subdirectories under each solution category:

```
├── docs/
│   └── solutions/
│       ├── data-quality-issues/
│       │   └── _archived/
│       ├── model-library-issues/
│       │   └── _archived/
│       ...
```

**Step 2: Add pruning config to .harnessrc template**

In `templates/.harnessrc.template`, add:

```yaml
# Knowledge pruning configuration
# pruning:
#   staleness_threshold_days: 90
#   auto_archive_superseded: true
```

**Step 3: Commit**

```bash
git add skills/harness-init/SKILL.md templates/.harnessrc.template
git commit -m "feat: add _archived dirs and pruning config to project scaffold"
```

---

## Epic 17: Isolated VM Execution Environment

### Task 17.1: Document VM setup requirements

**Files:**
- Create: `docs/infrastructure/vm-setup.md`

**Step 1: Write the VM setup guide**

```markdown
# Isolated VM Setup Guide

## Overview

The one-shot-build harness is designed to run on an isolated VM with
`--dangerously-skip-permissions` mode for fully autonomous operation.
**Never run in this mode on a developer's local machine.**

## Prerequisites

| Component | Version | Purpose |
|-----------|---------|---------|
| Ubuntu | 22.04+ | Base OS |
| Docker | 24+ | Local PySpark container |
| Claude Code | Latest | Agent runtime |
| Python | 3.10+ | Project dependencies |
| Git | 2.40+ | Version control |
| Databricks CLI | Latest | Cluster access |
| yq | 4.x | YAML processing |
| Node.js | 18+ | BATS test runner |

## Setup Steps

### 1. Install Claude Code
```bash
# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code
```

### 2. Configure permissions mode
```bash
# Launch with skip permissions (VM ONLY)
claude --dangerously-skip-permissions
```

### 3. Install the plugin
```bash
claude plugins install <plugin-repo-url>
```

### 4. Configure credentials
Set environment variables (never store in files):
```bash
export ANTHROPIC_API_KEY="..."
export DATABRICKS_TOKEN="..."
export GITHUB_TOKEN="..."
```

### 5. Verify Docker
```bash
docker run --rm pyspark-dev:latest spark-submit --version
```

### 6. Verify Databricks connectivity
```bash
databricks clusters get --cluster-id <id>
```

## Security Considerations

- VM should have no access to production databases or systems
- Network egress should be limited to: Anthropic API, GitHub, Databricks workspace
- Credentials should be injected via secrets manager, not baked into the VM image
- VM should auto-terminate after configurable idle timeout
- All agent activity is logged to `claude-progress.txt` and git history for auditability
```

**Step 2: Commit**

```bash
git add docs/infrastructure/vm-setup.md
git commit -m "docs: add isolated VM setup guide for autonomous execution"
```

### Task 17.2: Update .harnessrc template with execution config

**Files:**
- Modify: `templates/.harnessrc.template`

**Step 1: Add execution environment section**

```yaml
# Execution environment
# execution:
#   mode: autonomous              # autonomous | interactive
#   skip_permissions: true        # ONLY set to true on isolated VMs
#   vm_id: ""                    # set by provisioning automation
#   idle_timeout_minutes: 60     # auto-terminate after idle
```

**Step 2: Commit**

```bash
git add templates/.harnessrc.template
git commit -m "feat: add execution environment config to .harnessrc template"
```

### Task 17.3: Update session-start hook to warn if not on VM

**Files:**
- Modify: `hooks/session-start.sh`

**Step 1: Add environment check**

At the top of the session-start hook, after reading `.harnessrc`, check if `execution.skip_permissions` is `true` but no `vm_id` is set:

```bash
# Warn if dangerous mode detected without VM isolation
if [[ -f "$PROJECT_ROOT/.harnessrc" ]] && command -v yq &>/dev/null; then
    skip_perms=$(yq eval ".execution.skip_permissions" "$PROJECT_ROOT/.harnessrc" 2>/dev/null)
    vm_id=$(yq eval ".execution.vm_id" "$PROJECT_ROOT/.harnessrc" 2>/dev/null)
    if [[ "$skip_perms" == "true" && ( -z "$vm_id" || "$vm_id" == "null" ) ]]; then
        context+="\\n\\n⚠️ **WARNING:** skip_permissions is enabled but no vm_id is set.\\n"
        context+="Ensure you are running on an isolated VM, not a developer machine.\\n"
    fi
fi
```

**Step 2: Run tests to verify no regression**

Run: `npx bats tests/session_start_test.bats`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add hooks/session-start.sh
git commit -m "feat: add VM isolation warning to session-start hook"
```

---

## Epic 18: Databricks MCP Server + Skill

### Task 18.1: Create Databricks MCP server

**Files:**
- Create: `mcp/databricks-executor/server.py`
- Create: `mcp/databricks-executor/requirements.txt`
- Create: `mcp/databricks-executor/README.md`

**Step 1: Write requirements.txt**

```
mcp>=1.0.0
databricks-sdk>=0.20.0
pyyaml>=6.0
```

**Step 2: Write the MCP server**

```python
"""
Databricks Executor MCP Server
Exposes Databricks operations as MCP tools for the one-shot-build harness.
Reads configuration from .harnessrc in the current project directory.
"""

import os
import yaml
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.compute import State

app = Server("databricks-executor")


def load_config() -> dict:
    """Load Databricks config from .harnessrc."""
    harnessrc = Path.cwd() / ".harnessrc"
    if not harnessrc.exists():
        raise FileNotFoundError("No .harnessrc found. Run /init first.")
    with open(harnessrc) as f:
        config = yaml.safe_load(f)
    return config.get("databricks", {})


def get_client(config: dict) -> WorkspaceClient:
    """Create authenticated Databricks client."""
    token_var = config.get("token_env_var", "DATABRICKS_TOKEN")
    token = os.environ.get(token_var)
    if not token:
        raise ValueError(f"Environment variable {token_var} not set")
    return WorkspaceClient(
        host=config["workspace_url"],
        token=token,
    )


@app.tool()
async def execute_code(code: str, language: str = "python") -> list[TextContent]:
    """Execute a code snippet on the configured Databricks cluster.
    Returns the output of the execution."""
    config = load_config()
    client = get_client(config)
    cluster_id = config["cluster_id"]

    # Ensure cluster is running
    cluster = client.clusters.get(cluster_id)
    if cluster.state != State.RUNNING:
        client.clusters.start(cluster_id).result()

    # Execute via command API
    context = client.command.create(
        cluster_id=cluster_id,
        language=language,
        command=code,
    ).result()

    output = context.results.data if context.results else "No output"
    return [TextContent(type="text", text=str(output))]


@app.tool()
async def cluster_status() -> list[TextContent]:
    """Check the status of the configured Databricks cluster."""
    config = load_config()
    client = get_client(config)
    cluster = client.clusters.get(config["cluster_id"])
    return [TextContent(
        type="text",
        text=f"Cluster: {cluster.cluster_name}\nState: {cluster.state.value}\nID: {config['cluster_id']}",
    )]


@app.tool()
async def start_cluster() -> list[TextContent]:
    """Start the configured Databricks cluster if it's terminated."""
    config = load_config()
    client = get_client(config)
    cluster_id = config["cluster_id"]
    cluster = client.clusters.get(cluster_id)

    if cluster.state == State.RUNNING:
        return [TextContent(type="text", text="Cluster is already running.")]

    client.clusters.start(cluster_id).result()
    return [TextContent(type="text", text=f"Cluster {cluster_id} started successfully.")]


@app.tool()
async def upload_file(local_path: str, dbfs_path: str) -> list[TextContent]:
    """Upload a local file to DBFS."""
    config = load_config()
    client = get_client(config)
    with open(local_path, "rb") as f:
        client.dbfs.put(dbfs_path, f, overwrite=True)
    return [TextContent(type="text", text=f"Uploaded {local_path} to {dbfs_path}")]


@app.tool()
async def download_file(dbfs_path: str, local_path: str) -> list[TextContent]:
    """Download a file from DBFS to local filesystem."""
    config = load_config()
    client = get_client(config)
    with open(local_path, "wb") as f:
        for chunk in client.dbfs.read(dbfs_path).data:
            f.write(chunk)
    return [TextContent(type="text", text=f"Downloaded {dbfs_path} to {local_path}")]


@app.tool()
async def list_tables(catalog: str = "", schema: str = "") -> list[TextContent]:
    """List tables in a Databricks catalog/schema for data discovery."""
    config = load_config()
    client = get_client(config)
    cat = catalog or config.get("default_catalog", "main")
    sch = schema or config.get("default_schema", "default")
    tables = client.tables.list(catalog_name=cat, schema_name=sch)
    table_list = "\n".join(f"- {t.full_name}" for t in tables)
    return [TextContent(type="text", text=f"Tables in {cat}.{sch}:\n{table_list}")]


if __name__ == "__main__":
    import asyncio
    asyncio.run(app.run())
```

**Step 3: Write README**

```markdown
# Databricks Executor MCP Server

MCP server that exposes Databricks operations for the one-shot-build harness.

## Tools

| Tool | Description |
|------|-------------|
| `execute_code` | Run Python/SQL on a Databricks cluster |
| `cluster_status` | Check cluster state |
| `start_cluster` | Start a terminated cluster |
| `upload_file` | Upload to DBFS |
| `download_file` | Download from DBFS |
| `list_tables` | List tables in a catalog/schema |

## Configuration

Set in your project's `.harnessrc`:

```yaml
databricks:
  workspace_url: "https://adb-xxxx.azuredatabricks.net"
  cluster_id: "xxxx-xxxxxx-xxxxxxxx"
  default_catalog: "main"
  default_schema: "client_xyz"
  token_env_var: "DATABRICKS_TOKEN"
```

## Setup

```bash
pip install -r requirements.txt
export DATABRICKS_TOKEN="your-token"
```
```

**Step 4: Commit**

```bash
git add mcp/databricks-executor/
git commit -m "feat: add Databricks MCP server with execute, upload, cluster tools"
```

### Task 18.2: Register MCP server in plugin config

**Files:**
- Modify: `.claude-plugin/plugin.json`

**Step 1: Add MCP server registration**

Add to `plugin.json`:

```json
{
  "name": "one-shot-build",
  "description": "Workflow harness for autonomous client analytics project execution with Claude Code",
  "version": "0.1.0",
  "mcpServers": {
    "databricks-executor": {
      "command": "python",
      "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/databricks-executor/server.py"],
      "env": {}
    }
  }
}
```

**Step 2: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -m "feat: register Databricks MCP server in plugin manifest"
```

### Task 18.3: Create run-on-databricks skill

**Files:**
- Create: `skills/run-on-databricks/SKILL.md`

**Step 1: Write the skill**

```markdown
---
name: run-on-databricks
description: Use when you need to execute PySpark code on Databricks for full-scale data processing, or when local Docker execution is insufficient (large datasets, production validation, Unity Catalog access).
---

# Run on Databricks

## Overview

Execute PySpark code on a Databricks cluster for scaled data processing. Use this when local Docker is insufficient.

## When to Use Databricks vs Local Docker

| Scenario | Use |
|----------|-----|
| Data profiling on samples (<100MB) | Local Docker |
| Unit tests with test fixtures | Local Docker |
| Development iteration (write-test-fix loop) | Local Docker |
| Full-scale data processing (>1GB) | **Databricks** |
| Integration tests against real data | **Databricks** |
| Production validation before PR | **Databricks** |
| Accessing Unity Catalog tables | **Databricks** |
| Performance benchmarking | **Databricks** |

## Process

### 1. Check cluster status
Use the `cluster_status` MCP tool. If terminated, use `start_cluster`.

### 2. Execute code
Use the `execute_code` MCP tool with your PySpark code.

Important:
- Set catalog and schema at the start: `spark.sql("USE CATALOG main; USE SCHEMA client_xyz")`
- Use the same code that runs locally — no Databricks-specific rewrites
- If the code requires files, upload them first with `upload_file`

### 3. Validate results
Compare Databricks output against local test expectations.
If results differ between local and Databricks, this is a bug — investigate.

### 4. Download artifacts
Use `download_file` to pull any generated artifacts back to the project repo.

## Configuration

Databricks settings are in `.harnessrc` under the `databricks:` key.
The token is read from the environment variable specified in `token_env_var`.

## Important

- NEVER hardcode tokens or credentials in code or config files
- Always develop and test locally FIRST, then validate on Databricks
- Databricks execution is slower and costs money — use it intentionally
- If a cluster start fails, check with the human before retrying
```

**Step 2: Commit**

```bash
git add skills/run-on-databricks/SKILL.md
git commit -m "feat: add run-on-databricks skill for local vs cluster decision guidance"
```

### Task 18.4: Update .harnessrc template with Databricks config

**Files:**
- Modify: `templates/.harnessrc.template`

**Step 1: Add Databricks section**

```yaml
# Databricks integration
# databricks:
#   workspace_url: "https://adb-xxxx.azuredatabricks.net"
#   cluster_id: "xxxx-xxxxxx-xxxxxxxx"
#   default_catalog: "main"
#   default_schema: "client_xyz"
#   token_env_var: "DATABRICKS_TOKEN"
```

**Step 2: Commit**

```bash
git add templates/.harnessrc.template
git commit -m "feat: add Databricks config section to .harnessrc template"
```

---

## Epic 19: Kanban Dashboard

### Task 19.1: Create dashboard HTML/CSS/JS

**Files:**
- Create: `dashboard/index.html`
- Create: `dashboard/style.css`
- Create: `dashboard/app.js`
- Create: `dashboard/package.json`

**Step 1: Write package.json**

```json
{
  "name": "one-shot-build-dashboard",
  "version": "0.1.0",
  "private": true,
  "dependencies": {
    "js-yaml": "^4.1.0"
  }
}
```

**Step 2: Write index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>One-Shot Build — Kanban Board</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header>
        <h1 id="project-name">One-Shot Build</h1>
        <div id="summary-bar">
            <span id="phase-badge" class="badge">Phase: —</span>
            <span id="epic-badge" class="badge">Epic: —</span>
            <span id="progress-badge" class="badge">Progress: —</span>
            <span id="circuit-badge" class="badge">Circuit: CLOSED</span>
        </div>
    </header>

    <div id="filters">
        <label>Epic: <select id="filter-epic"><option value="all">All Epics</option></select></label>
        <label>Status: <select id="filter-status">
            <option value="all">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="blocked">Blocked</option>
        </select></label>
        <label>Gate: <select id="filter-gate">
            <option value="all">All Gates</option>
            <option value="tests_pending">Tests Pending</option>
            <option value="review_pending">Review Pending</option>
            <option value="both_pass">Both Pass</option>
        </select></label>
        <label><input type="checkbox" id="show-steps" checked> Show Steps</label>
    </div>

    <div id="board">
        <div class="column" data-status="pending">
            <h2>Pending</h2>
            <div class="card-container"></div>
        </div>
        <div class="column" data-status="plan">
            <h2>Planning</h2>
            <div class="card-container"></div>
        </div>
        <div class="column" data-status="in_progress">
            <h2>Building</h2>
            <div class="card-container"></div>
        </div>
        <div class="column" data-status="review">
            <h2>In Review</h2>
            <div class="card-container"></div>
        </div>
        <div class="column" data-status="completed">
            <h2>Complete</h2>
            <div class="card-container"></div>
        </div>
        <div class="column" data-status="blocked">
            <h2>Blocked</h2>
            <div class="card-container"></div>
        </div>
    </div>

    <footer>
        <span id="last-updated">Last updated: —</span>
        <span id="auto-refresh">Auto-refresh: 5s</span>
    </footer>

    <script src="node_modules/js-yaml/dist/js-yaml.min.js"></script>
    <script src="app.js"></script>
</body>
</html>
```

**Step 3: Write style.css**

The CSS should implement:
- A 6-column Kanban layout (flexbox or CSS grid)
- Card styling with color coding (green=complete, blue=in-progress, yellow=review-pending, red=blocked, gray=pending)
- Epic cards with expandable step sub-cards
- Responsive layout
- Dark/light mode support
- Badge styling for the summary bar
- Filter bar styling

**Step 4: Write app.js**

The JavaScript should implement:
- `loadState(path)` — fetch and parse `project-state.yaml` via the local server
- `renderBoard(state, filters)` — clear and re-render all cards into columns
- `createEpicCard(epic)` — render an epic as a card with status, step count, gates
- `createStepCard(step)` — render a step as a sub-card within an epic
- `applyFilters()` — read filter dropdowns and re-render
- `autoRefresh(interval)` — poll for state changes every N seconds
- `updateSummaryBar(state)` — update header badges from state
- Filter logic for epic, status, and gate dropdowns

**Step 5: Install dependencies and commit**

```bash
cd dashboard && npm install && cd ..
git add dashboard/
git commit -m "feat: add Kanban dashboard with filtering, auto-refresh, color-coded cards"
```

### Task 19.2: Create dashboard server script

**Files:**
- Create: `dashboard/serve.sh`

**Step 1: Write the server script**

```bash
#!/usr/bin/env bash
# dashboard/serve.sh
# Launches a local HTTP server for the Kanban dashboard.
# Serves both the dashboard files AND the project's state file.
# Usage: serve.sh [project-root] [port]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PROJECT_ROOT="${1:-$(pwd)}"
PORT="${2:-8080}"

# Create a temp directory with symlinks so the server can access both
SERVE_DIR=$(mktemp -d)
ln -s "$SCRIPT_DIR"/* "$SERVE_DIR/" 2>/dev/null || true
ln -s "$PROJECT_ROOT/project-state.yaml" "$SERVE_DIR/project-state.yaml" 2>/dev/null || true

echo "Kanban Dashboard: http://localhost:${PORT}"
echo "Project root: $PROJECT_ROOT"
echo "Press Ctrl+C to stop."

# Serve with Python's built-in HTTP server
cd "$SERVE_DIR"
python3 -m http.server "$PORT" --bind 127.0.0.1

# Cleanup on exit
trap "rm -rf $SERVE_DIR" EXIT
```

**Step 2: Make executable**

```bash
chmod +x dashboard/serve.sh
```

**Step 3: Commit**

```bash
git add dashboard/serve.sh
git commit -m "feat: add dashboard server script with project state symlink"
```

### Task 19.3: Create /board command

**Files:**
- Create: `commands/board.md`

**Step 1: Write the command**

```markdown
---
description: "Launch the Kanban dashboard to visualize project progress."
disable-model-invocation: true
---

Launch the one-shot-build Kanban dashboard by running:

```bash
bash <plugin_root>/dashboard/serve.sh $(pwd) 8080
```

Then open http://localhost:8080 in your browser.

The dashboard reads project-state.yaml and auto-refreshes every 5 seconds.
Use the filters to view by epic, status, or gate state.
```

**Step 2: Commit**

```bash
git add commands/board.md
git commit -m "feat: add /board command to launch Kanban dashboard"
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
| 13 | 13.1-13.4 | Compound learning — solution doc schema, validation with contradiction detection, scaffolding (TDD) |
| 14 | 14.1-14.5 | Learnings researcher agent (version-gated) + knowledge retrieval + promotion |
| 15 | 15.1-15.2 | Self-verification CLI + final hook wiring |
| 16 | 16.1-16.3 | Knowledge pruning — `/prune-knowledge` skill, command, scaffold updates |
| 17 | 17.1-17.3 | Isolated VM environment — setup guide, config, session-start safety warning |
| 18 | 18.1-18.4 | Databricks MCP server + skill + plugin registration + config |
| 19 | 19.1-19.3 | Kanban dashboard — HTML/CSS/JS app, server script, `/board` command |

**Total: 19 epics, 48 tasks**
