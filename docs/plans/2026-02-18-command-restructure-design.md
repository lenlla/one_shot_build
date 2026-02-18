# Command Restructure Design

**Date:** 2026-02-18
**Status:** Approved
**Approach:** A — Refactor existing skills

## Overview

Replace the `/next`-driven linear workflow with explicit commands that give the analyst direct control over each phase. Remove global phase tracking. Scope execution state to the epics directory.

## Command Surface

| Command | Arguments | Behavior |
|---------|-----------|----------|
| `/init` | *(unchanged)* | Scaffold new project from templates |
| `/profile-data` | `[table paths...]` (optional) | If table paths provided, profiles those. If not, asks for table locations. Supports multiple tables. Creates one `data-profile-<table>.md` per table. If a profile already exists for a table, asks: overwrite or new version. |
| `/define-epics` | `[context paths...]` (optional) | Brainstorming flow — opens with "What do you want to build today?" Context paths accepted as args or requested interactively. If data profile among context, asks targeted data questions. Collaboratively breaks down work into epics. Asks analyst to name output directory. Saves epic YAML specs there. |
| `/execute-plan` | `<epics-dir>` (required — prompt if missing) | Interactive mode. Context usage check at startup with clear instructions. Loops through epics: plan -> build -> submit. Pauses for human input at key points. On re-run, shows progress and asks resume vs start fresh. |
| `/execute-plan-autonomously` | `<epics-dir>` (required — prompt if missing) | Same loop but auto-advancing. Front-loads `--dangerously-skip-permissions` check. If not detected: explains the flag, shows restart command, asks if they want to proceed anyway. |

**Removed:** `/next`

**Unchanged:** `/status`, `/board`, `/prune-knowledge`

## State Management

### Global phase tracking removed

No `project-state.yaml`. The analyst drives `profile-data` -> `define-epics` -> `execute-plan` manually. State tracking only exists during execution.

### Execution state scoped to epics directory

Created when `execute-plan` first runs against a directory. Lives at `<epics-dir>/.execution-state.yaml`.

```yaml
# epics/v1/.execution-state.yaml
started_at: "2026-02-18T14:30:00Z"
mode: interactive  # or autonomous
epics:
  data-loading:
    status: completed          # pending | planning | building | submitting | completed
    branch: epic/data-loading
    pr: 42
    completed_at: "2026-02-18T15:10:00Z"
  transformation:
    status: building
    current_step: 3
    steps_total: 5
    circuit_breaker:
      review_rounds: 2
      same_errors: 0
      no_progress: 0
  model-execution:
    status: pending
  report-generation:
    status: pending
```

### Resume behavior

When `execute-plan` is invoked on a directory with an existing `.execution-state.yaml`:

1. Read the state file
2. Show summary: "2 of 4 epics completed, currently on 'transformation' step 3/5"
3. Ask: resume from where you left off, or start fresh?
4. "Start fresh" deletes the state file and begins again

### Concurrent execution warning

If another `.execution-state.yaml` with incomplete epics is detected elsewhere in the project, warn the user and ask for confirmation before proceeding. Concurrent executions against the same codebase risk branch and merge conflicts.

## Skill Refactoring

### `gather-context` skill (backend for `/profile-data`)

- Strip analyst Q&A portion
- Keep profiler agent dispatch logic
- Add: accept table paths as input, loop over multiple tables
- Add: per-table output naming (`data-profile-<table>.md`)
- Add: existing profile detection — prompt for overwrite vs new version
- Remove: dependency on `project-state.yaml`

### `define-epics` skill (backend for `/define-epics`)

- Open with brainstorming flow: "What do you want to build today?"
- Accept context paths as args or ask for them interactively
- If data profile among context, transition to targeted data questions
- Collaborative Q&A — one question at a time, multiple choice preferred
- Once clear picture formed, propose epic breakdown with trade-offs
- Iterative refinement with analyst
- Ask analyst to name output directory, save epic YAML specs there
- Keep: knowledge base search (learnings-researcher)
- Remove: dependency on `project-state.yaml`

### `plan-epic` skill (called by orchestrator per epic)

- Accept epic spec path and epics directory as parameters (not global state)
- Write planning artifacts relative to the epic
- Keep: TDD baseline tagging, learnings-researcher search, test-first approach
- Remove: dependency on global phase/epic state

### `build-step` skill (called by orchestrator per epic)

- Accept epic context as parameters
- Circuit breaker state read/written to `.execution-state.yaml`
- Keep: agent team architecture (lead/developer/reviewer), circuit breaker logic, review loops, solution docs, stuck-loop detection
- Remove: dependency on global state

### `submit-epic` skill (called by orchestrator per epic)

- Read/write state from `.execution-state.yaml`
- Mode (interactive/autonomous) passed as parameter by orchestrator
- Keep: DoD checks, quality scan, PR creation, knowledge promotion
- Remove: dependency on global state and `.harnessrc` for mode

### New: `execute-plan` skill (orchestrator)

See Orchestration Loop section below.

## Execute-Plan Orchestration Loop

### Agent architecture

The orchestrator is purely a coordinator. All heavy work is delegated to sub-agents to preserve the orchestrator's context window.

```
Orchestrator (main agent):
  - Manages the epic loop and state
  - Handles pause points, user interaction, resume logic
  - Dispatches sub-agents for ALL heavy work
  - Monitors circuit breakers
  - Stays lean on context throughout

for each pending/incomplete epic:
    1. Plan epic    -> sub-agent
    2. Build epic   -> sub-agents (developer + reviewer)
    3. Submit epic  -> sub-agent

    Orchestrator updates .execution-state.yaml between each phase.
```

### Startup sequence (both modes)

1. Parse epics directory argument (prompt if missing)
2. Check for concurrent executions — scan for other active `.execution-state.yaml` files. Warn and confirm if found.
3. Check context usage % — if high, recommend clearing with instructions (`/clear` or fresh session)
4. **Autonomous only:** Check for `--dangerously-skip-permissions`. If not detected, explain the flag, show restart command (`claude --dangerously-skip-permissions`), ask if they want to proceed anyway.
5. Check for existing `.execution-state.yaml` in target directory:
   - If exists: show progress summary, ask resume vs start fresh
   - If not: read epic YAML specs from directory, create `.execution-state.yaml` with all epics as `pending`

### Main loop

```
for each pending/incomplete epic:
    1. Plan epic -> SUB-AGENT
       - Dispatched with: epic spec, project context, epics dir
       - Does: knowledge search, test writing, TDD baseline tag, implementation plan
       - Returns: confirmation + summary
       - Orchestrator updates state: epic status -> "building"

    2. Build epic -> SUB-AGENTS (developer + reviewer)
       - Same agent team architecture as today
       - Orchestrator monitors circuit breakers
       - Orchestrator updates state: step progress, circuit breaker counts

    3. Submit epic -> SUB-AGENT
       - Dispatched with: epic context, mode, epics dir
       - Does: DoD checks, quality scan, PR creation
       - Returns: PR number + summary
       - Orchestrator updates state: epic status -> "completed", records PR ref
```

### Pause points — interactive mode

- Before starting each epic: "Next up: 'transformation' (2 of 4). Proceed?"
- After PR creation: "PR #42 created. Merge when ready, then confirm to continue."
- On circuit breaker trip: "Build stuck on 'transformation' step 3. Review rounds: 5/5. What would you like to do?"

### Pause points — autonomous mode

- On circuit breaker trip only (everything else auto-advances)
- On merge failure: halt and log

### Error handling

- Circuit breaker trips: halt current epic, surface state to user regardless of mode
- Merge conflicts: halt, notify, show state
- Test failures in DoD: interactive asks user, autonomous attempts auto-fix then retries

## File Changes

### New files

| File | Purpose |
|------|---------|
| `commands/profile-data.md` | `/profile-data` slash command entry point |
| `commands/define-epics.md` | `/define-epics` slash command entry point |
| `commands/execute-plan.md` | `/execute-plan` slash command entry point |
| `commands/execute-plan-autonomously.md` | `/execute-plan-autonomously` slash command entry point |
| `skills/execute-plan/SKILL.md` | Orchestrator skill |

### Modified files

| File | Changes |
|------|---------|
| `skills/gather-context/SKILL.md` | Strip Q&A, add multi-table support, per-table naming, existing profile detection |
| `skills/define-epics/SKILL.md` | Add brainstorming flow, context-gathering, data questions, directory naming |
| `skills/plan-epic/SKILL.md` | Accept parameters instead of global state |
| `skills/build-step/SKILL.md` | Accept parameters, circuit breaker writes to `.execution-state.yaml` |
| `skills/submit-epic/SKILL.md` | Accept parameters, mode passed in |
| `hooks/session-start.sh` | Scan for `.execution-state.yaml` files, list all active executions |
| `hooks/definition-of-done.sh` | Accept epics directory path as argument |
| `hooks/check-test-immutability.sh` | Accept baseline tag name as argument |
| `hooks/self-check.sh` | Pass epics directory path through to sub-hooks |
| `commands/status.md` | Scan for all `.execution-state.yaml` files, list summaries |
| `dashboard/app.js` | Read from `.execution-state.yaml`, add directory selector for multiple |
| `templates/.harnessrc.template` | Remove `execution.mode` field |
| `templates/CLAUDE.md.template` | Update quick-start to reference new commands |
| `lib/state.sh` | Refactor to read/write `.execution-state.yaml` at a given path |
| `tests/*.bats` | Update fixtures for new state model |

### Removed files

| File | Reason |
|------|--------|
| `commands/next.md` | Replaced by explicit commands |
| `templates/project-state.yaml.template` | Replaced by `.execution-state.yaml` in epics directory |

## Hooks & Enforcement

### `session-start.sh` — Major refactor

- Scan project for `.execution-state.yaml` files
- If one active execution: show it with resume command
- If multiple active: list all, let user choose by running `execute-plan <dir>`
- If none active: inject minimal context (project name, available commands)

### `definition-of-done.sh` — Minor refactor

- Accept epics directory path as argument (passed by orchestrator)
- Core checks unchanged

### `check-test-immutability.sh` — Minor refactor

- Accept baseline tag name as argument
- Core logic unchanged

### `quality-scan.sh` — Minimal change

- Codebase-wide checks, not state-dependent
- Path updates only if needed

### `validate-solution-doc.sh` — No change

### `self-check.sh` — Minor update

- Pass epics directory path through to sub-hooks
