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
