---
name: submit-epic
description: Use when all steps in the current epic are built and reviewed. Runs the definition-of-done checklist and creates a PR. Requires current_phase to be submit.
---

# Submit Epic

## Overview

Phase 5 of the one-shot-build workflow. Run final quality checks and submit a PR for the completed epic.

## Pre-Conditions

- `kyros-agent-workflow/project-state.yaml` shows `workflow.current_phase: submit`
- All steps in the current epic have `tests_pass: true` and `review_approved: true`

## Process

### Step 1: Read execution mode

Read `kyros-agent-workflow/.harnessrc` and check `execution.mode`. This determines behavior throughout this skill:
- `interactive` (default): pause for human input on failures and learnings promotion
- `autonomous`: auto-fix failures and auto-promote universal learnings without waiting

### Step 2: Run Definition of Done

Execute the DoD checklist:
```bash
bash <plugin_root>/hooks/definition-of-done.sh
```

**If it fails:**
- **Interactive mode:** Show the failures and ask the user how to proceed.
- **Autonomous mode:** Attempt to fix each failure automatically:
  - TODO comments → remove them or replace with proper implementation
  - Debug print statements → remove them
  - Unapproved steps → check if review was missed, re-run reviewer
  - Empty/missing `kyros-agent-workflow/claude-progress.txt` → write the epic summary
  - After fixing, re-run the DoD check. If it fails again after 3 attempts, halt and log the failure to `kyros-agent-workflow/claude-progress.txt`.

### Step 3: Run quality scan

Execute a quality scan to catch any drift:
```bash
bash <plugin_root>/hooks/quality-scan.sh
```

**If findings are reported:**
- **Interactive mode:** Flag findings but don't block the PR. Present auto-fixable vs manual issues to the user.
- **Autonomous mode:** Automatically fix what can be fixed (unused imports, formatting violations). For issues that cannot be auto-fixed (missing type hints), include them in the PR description as known items. Commit any fixes before proceeding.

### Step 4: Promote cross-project learnings

Review `kyros-agent-workflow/docs/solutions/` for solution docs created during this epic.

For each doc where `applies_to.scope` is `universal` or the content is clearly not project-specific:

- **Interactive mode:**
  1. Present to the user: "These solutions from this epic might help future projects:"
     - [title] → [category/filename]
  2. If the user approves promotion and `shared_knowledge_path` is configured in `kyros-agent-workflow/.harnessrc`:
     - Copy the solution doc to `<shared_knowledge_path>/docs/solutions/<category>/`
     - Commit to the shared repo
     - Create a PR (or push directly if configured)
  3. If no shared knowledge path is configured, suggest the user set one up.

- **Autonomous mode:**
  1. If `shared_knowledge_path` is configured, automatically promote all docs with `applies_to.scope: universal`.
  2. Log promoted docs to `kyros-agent-workflow/claude-progress.txt`.
  3. If no shared knowledge path is configured, skip and note in the PR description.

### Step 5: Create the PR

Generate a PR using `gh pr create`:
- Title: "Epic: [epic-name]"
- Body: Summary of what was built, list of steps completed, test results, any quality scan findings
- Base branch: main (or as configured)

### Step 6: Update state

- Set `epics.<current_epic>.status: completed`
- Set `epics.<current_epic>.pr: "#<pr_number>"`
- Determine the next epic:
  - If there are more epics with `status: pending`: set it as `current_epic`, set `current_phase: plan`
  - If all epics are complete: set `current_phase: done`
- Clear `current_step`

### Step 7: Commit state and log

```bash
git add kyros-agent-workflow/project-state.yaml kyros-agent-workflow/claude-progress.txt
git commit -m "chore: mark epic <name> complete, advance to next"
```

### Step 8: Advance or report

**Interactive mode:**
- If more epics remain: "PR created: [URL]. Once merged, run `/plan-epic` to start the next epic."
- If all epics complete: "All epics complete! Final PR: [URL]. Project is done pending human review."

**Autonomous mode:**
- If more epics remain: Log "Advancing to next epic" and automatically invoke the `plan-epic` skill to continue without waiting.
- If all epics complete: Log "All epics complete" to `kyros-agent-workflow/claude-progress.txt` and halt.
