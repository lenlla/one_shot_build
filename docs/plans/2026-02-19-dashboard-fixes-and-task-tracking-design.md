# Dashboard Fixes and Task Tracking Design

**Date:** 2026-02-19
**Status:** Approved

## Problem

Recent changes to progress tracking (per-task agents, step-level state, per-execution directories) introduced a mismatch between what the dashboard expects and what the state library writes. Additionally, the dashboard only shows epic-level cards and lacks individual task tracking.

### Bug 1: Step completion field mismatch

The dashboard (`app.js`) checks `step.tests_pass && step.review_approved` booleans to determine step completion (progress bars, gate dots, gate filters). However, `build-step/SKILL.md` only sets `step.status = "completed"` via `update_step_status`. The gate boolean fields are never written. Result: progress bars show 0%, gate dots always red, gate filtering broken.

### Bug 2: `serve.sh` only links first state file

`serve.sh` uses `find ... | break` to symlink only the first `.execution-state.yaml`. With per-execution directories, only one build is visible.

### Gap: No individual task tracking

Tasks (steps within epics) only appear as sub-cards under epic cards. Users want to see individual tasks in their own Kanban columns.

## Design

### Fix 1: State-to-dashboard field sync (fix both sides)

**build-step/SKILL.md changes:**
- After developer reports TESTS: PASS, set `tests_pass: true` on the step:
  `update_execution_state "<build_dir>" "epics.<epic>.steps.<step>.tests_pass" "true"`
- After reviewer approves, set `review_approved: true` on the step:
  `update_execution_state "<build_dir>" "epics.<epic>.steps.<step>.review_approved" "true"`

**app.js changes:**
- Update step completion counting to use `step.status === 'completed'` as primary indicator, with gate booleans as supplementary
- `createStepCard`: show status-based color indicator in addition to gate dots
- Handle missing gate fields gracefully (treat undefined as false)

### Fix 2: `serve.sh` build directory targeting

- Accept `--build-dir` argument to target a specific build directory's state file
- Fall back to searching PROJECT_ROOT for the first state file if no argument given
- The `/board` command can pass the active build directory

### Feature: Tab toggle (Epics vs Tasks view)

**HTML:**
- Tab bar above the board: `[Epics] [Tasks]`
- Both tabs reuse the same 6-column layout

**JS:**
- `renderTaskBoard(state, filters)` function: iterates all epics -> all steps, creates individual task cards placed in columns based on step status:
  - `pending` -> Pending column
  - `in_progress` -> Building column
  - `completed` (or both gates pass) -> Complete column
- Task cards show: task name, parent epic label (subtle tag), gate dots, review round count, status indicator
- Tab toggle re-renders board in selected mode
- Filters work in both views: epic filter narrows to tasks from that epic

**CSS:**
- Tab bar styling (active/inactive states)
- Task card styling (distinct from epic cards: smaller, different accent, parent epic tag)
- Status indicators: pending=gray, in_progress=blue, completed=green

### Enhancement: Step status indicators

In both views, step/task cards show:
- Colored status dot (pending/in_progress/completed)
- Review round count badge if > 0
- Gate dots (tests/review) when those fields exist

## Files Changed

| File | Change |
|------|--------|
| `dashboard/app.js` | Fix step counting, add task board rendering, tab toggle logic |
| `dashboard/index.html` | Add tab bar markup |
| `dashboard/style.css` | Tab bar styling, task card styling, status indicators |
| `dashboard/serve.sh` | Support build-dir argument |
| `skills/build-step/SKILL.md` | Add gate field writes after test pass and review approval |
| `tests/state_test.bats` | Add tests for gate field expectations |
