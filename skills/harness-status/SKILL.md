---
name: harness-status
description: Use when the user wants to check the current workflow state, see active executions, and what to do next.
---

# Harness Status

## Overview

Display the current execution state by scanning for `.execution-state.yaml` files and suggest the next action.

## Process

1. **Check for harness project** — Look for a `kyros-agent-workflow/` directory. If not found, tell the user to run `/init`.
2. **Find execution states** — Source `<plugin_root>/lib/state.sh` and call `find_execution_states` to locate all `.execution-state.yaml` files.
3. **Display status** — Based on what's found, show the appropriate output.

## Output: No Executions Found

If no `.execution-state.yaml` files exist:

```
## Workflow Status

No executions in progress.

### Next Action
- Run `/profile-data` to profile your data
- Run `/define-epics` to define project epics
- Run `/execute-plan <epics-dir>` to start executing epics
```

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

## Output: All Epics Complete

If execution states exist but all epics in all of them are completed:

```
## Workflow Status

All executions complete!

| Execution | Epics | PRs |
|-----------|-------|-----|
| <epics-dir> | N epics | PR #1, PR #2, ... |

### Next Action
- Run `/define-epics` to start a new round of work
- Run `/prune-knowledge` to clean up solution docs
```

## Edge Cases

- If no `kyros-agent-workflow/` directory exists: tell the user to run `/init`
- If `kyros-agent-workflow/` exists but no execution states: project is initialized but no executions started yet
- If circuit breaker is flagged in an execution state: warn and show the failure context
