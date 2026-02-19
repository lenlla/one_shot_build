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
- **build_dir**: Path to the build directory
- **mode**: `interactive` or `autonomous`
- **tdd_baseline_tag**: Git tag for immutability checks

## Process

### Step 1: Run Definition of Done

Execute the DoD checklist:
```bash
bash <plugin_root>/hooks/definition-of-done.sh <build_dir>
```

**If it fails:**
- **Interactive mode:** Report failures back to orchestrator for human review.
- **Autonomous mode:** Categorize each failure:
  - **Superficial failures** (TODO comments, debug prints, empty progress file): fix directly — remove TODOs, remove debug prints, write epic summary. Re-run DoD. Retry up to 3 times.
  - **Code-level failures** (test failures, implementation issues, regressions): do NOT attempt to fix. Report back to orchestrator immediately with:
    - `needs_code_fix: true`
    - The specific failure output (which tests failed, what the errors are)
    - Any relevant file paths

  If superficial fixes still fail after 3 attempts, report back to orchestrator with the failure details.

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
- **Autonomous mode:** If `shared_knowledge_path` is configured, automatically promote. Log to `<build_dir>/claude-progress.txt`.

### Step 4: Commit final state

```bash
git add <build_dir>/claude-progress.txt
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
