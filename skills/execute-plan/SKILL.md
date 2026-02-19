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

If the resumed epic is in `building` status and has step-level state, also show:
"Step progress for '<epic-name>':
- task-1-load-csv: completed
- task-2-validate-schema: in_progress (review round 2)
- task-3-type-casting: pending

The build will resume from '<next-pending-step>'."

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

Also create `<epics_dir>/claude-progress.txt` with a header line if it doesn't exist:

```
# Claude Progress Log — <epics_dir>
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
  - mode: `<interactive|autonomous>`
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

**If the sub-agent reports `needs_code_fix: true` (autonomous mode only):**

Re-dispatch the build-step sub-agent to fix the issue:
- Prompt: Invoke the build-step skill with the failure context — which tests failed, the error output, and the files involved. Instruct it to fix the failing tests without modifying test files.
- Wait for completion

Then re-dispatch submit-epic. This build→submit retry loop runs a maximum of 2 times. If submit still fails after 2 retries, halt and surface the issue to the user.

When sub-agent returns successfully, capture the PR number/URL from its report.

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

**Autonomous mode:** Log completion to `<epics_dir>/claude-progress.txt`. "All epics complete. Execution finished."

## Error Handling

- **Circuit breaker trip:** Halt and surface to user regardless of mode
- **Merge conflict:** Halt and notify
- **Sub-agent failure:** Log context, halt, surface to user
- **Permission denial in autonomous mode:** Warn about --dangerously-skip-permissions flag
