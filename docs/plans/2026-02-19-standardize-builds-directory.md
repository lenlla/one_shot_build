# Standardize Builds Directory Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the free-form `epics_dir` convention with a standardized `kyros-agent-workflow/builds/<name>/` directory structure containing `epic-specs/` and `plans/` subdirectories.

**Architecture:** Rename the concept from `epics_dir` to `build_dir` across all skills, commands, hooks, and tests. Epic YAML specs move to `<build_dir>/epic-specs/`, implementation plans move to `<build_dir>/plans/`. State files (`.execution-state.yaml`, `claude-progress.txt`) stay at the `<build_dir>/` root. The `lib/state.sh` functions already take a directory parameter, so they just need variable renaming.

**Tech Stack:** Bash (lib/state.sh, hooks), Markdown (skills, commands), BATS (tests)

---

### Task 1: Rename `epics_dir` to `build_dir` in `lib/state.sh`

**Files:**
- Modify: `lib/state.sh`

This is a variable rename only — the functions already accept a directory path parameter. No logic changes needed.

**Step 1: Update variable names and comments**

Replace all instances of `epics_dir` with `build_dir` and update comments to reference the new directory structure:

```bash
# In every function signature and local variable:
# epics_dir -> build_dir
# "epics directory" -> "build directory"
```

Specific changes in `lib/state.sh`:
- Line 13 comment: "epics directory" → "build directory"
- Line 14 function `log_progress`: parameter `epics_dir` → `build_dir`
- Line 16: `local epics_dir` → `local build_dir`
- Line 28 comment: "epics directory" → "build directory"
- Line 29 function `execution_state_file`: `epics_dir` → `build_dir`
- Line 30: `local epics_dir` → `local build_dir`
- Line 31: `echo "${epics_dir}/...` → `echo "${build_dir}/...`
- Line 35 comment + function `read_execution_state`: same rename
- Line 64 comment + function `update_execution_state`: same rename
- Line 88 function `find_execution_states`: no change (no `epics_dir` parameter)
- Line 93 function `find_active_executions`: rename `epics_dir` → `build_dir` on line 103
- Line 115 function `execution_summary`: rename `epics_dir` → `build_dir`
- Line 152 comment + function `read_step_status`: rename
- Line 161 comment + function `update_step_status`: rename
- Line 174 comment + function `init_steps_from_plan`: rename `epics_dir` → `build_dir`
- Line 209 comment + function `get_next_pending_step`: rename
- Line 227 comment + function `increment_review_rounds`: rename

**Step 2: Run tests to verify rename doesn't break anything**

Run: `cd /home/kyrosadmin/repos/one_shot_build && npx bats tests/state_test.bats`
Expected: All tests pass (tests pass directory paths positionally, so variable names don't matter)

**Step 3: Commit**

```bash
git add lib/state.sh
git commit -m "refactor: rename epics_dir to build_dir in lib/state.sh"
```

---

### Task 2: Update `tests/state_test.bats` to use new directory structure

**Files:**
- Modify: `tests/state_test.bats`

Update test fixtures to use `kyros-agent-workflow/builds/<name>/` structure with `epic-specs/` and `plans/` subdirectories. Also rename `epics_dir`-style paths in test setup.

**Step 1: Update test directory paths**

Change all test fixture paths from `$TEST_DIR/epics/v1` to `$TEST_DIR/kyros-agent-workflow/builds/v1`. The mock plan file in `init_steps_from_plan` test should move from `$TEST_DIR/kyros-agent-workflow/docs/plans/` to `$TEST_DIR/kyros-agent-workflow/builds/v1/plans/`.

Specific changes:

- `setup()` function (line 12): already creates `$PROJECT_ROOT/kyros-agent-workflow` — keep this
- Test "log_progress appends..." (line 24-31): `$TEST_DIR/epics/v1` → `$TEST_DIR/kyros-agent-workflow/builds/v1`
- Test "log_progress includes timestamp" (line 33-41): same
- Test "execution_state_file returns correct path" (line 45-49): `/tmp/epics/v1` → `/tmp/kyros-agent-workflow/builds/v1`
- Test "read_execution_state returns empty..." (line 51-55): `/tmp/nonexistent` is fine (tests missing file)
- Test "read_execution_state reads epic status" (line 57-73): `$TEST_DIR/epics/v1` → `$TEST_DIR/kyros-agent-workflow/builds/v1`
- Test "update_execution_state writes..." (line 75-87): same
- Test "find_execution_states finds..." (line 89-98): `$TEST_DIR/epics/v1`, `v2` → `$TEST_DIR/kyros-agent-workflow/builds/v1`, `builds/v2`
- Test "find_active_executions..." (line 100-117): same
- Test "execution_summary shows progress" (line 119-137): same
- Test "read_step_status returns empty..." (line 141-151): same
- Test "read_step_status returns step status" (line 153-168): same
- Test "update_step_status sets..." (line 170-185): same
- Test "init_steps_from_plan..." (line 187-230):
  - State file: `$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml`
  - Plan file: `$TEST_DIR/kyros-agent-workflow/builds/v1/plans/data-loading-plan.md` (was `$TEST_DIR/kyros-agent-workflow/docs/plans/data-loading-plan.md`)
- Test "get_next_pending_step..." (line 232-249): same path pattern
- Test "get_next_pending_step returns empty..." (line 251-266): same
- Test "increment_review_rounds..." (line 268-284): same
- Test "execution_summary includes step progress" (line 286-305): same

**Step 2: Run tests to verify**

Run: `cd /home/kyrosadmin/repos/one_shot_build && npx bats tests/state_test.bats`
Expected: All tests pass

**Step 3: Commit**

```bash
git add tests/state_test.bats
git commit -m "test: update state_test fixtures to use builds/ directory structure"
```

---

### Task 3: Update `skills/define-epics/SKILL.md`

**Files:**
- Modify: `skills/define-epics/SKILL.md`

The define-epics skill currently asks the user to name an arbitrary directory. It needs to:
1. Ask for just the build name (not a full path)
2. Create the directory at `kyros-agent-workflow/builds/<name>/`
3. Write epic specs to `kyros-agent-workflow/builds/<name>/epic-specs/`
4. Update the final instructions to reference the new path

**Step 1: Update the skill**

Changes:
- **Step 7** (line 74-78): Change from asking for a full directory path to asking for a build name. Create `kyros-agent-workflow/builds/<name>/epic-specs/`.

  Old:
  ```
  Use AskUserQuestion: "What should I name the epics directory? This is where the epic specs will be saved and where `/execute-plan` will look for them. Examples: `epics/v1`, `epics/initial-model`, `epics/feature-x`"
  Create the directory.
  ```

  New:
  ```
  Use AskUserQuestion: "What should I name this build? Examples: `v1`, `initial-model`, `feature-x`"
  Create the build directory at `kyros-agent-workflow/builds/<name>/epic-specs/`.
  ```

- **Step 8** (line 82-96): Change directory reference from `<epics-dir>` to `kyros-agent-workflow/builds/<name>/epic-specs/`:

  Old:
  ```yaml
  # <epics-dir>/01-<epic-name>.yaml
  ```

  New:
  ```yaml
  # kyros-agent-workflow/builds/<name>/epic-specs/01-<epic-name>.yaml
  ```

- **Step 9** (line 98-105): Update commit path and final user message:

  Old:
  ```
  git add <epics-dir>/
  git commit -m "docs: define epics in <epics-dir>"
  Tell the user: "Epics defined in `<epics-dir>/`. When you're ready to start building, run `/execute-plan <epics-dir>` or `/execute-plan-autonomously <epics-dir>`."
  ```

  New:
  ```
  git add kyros-agent-workflow/builds/<name>/
  git commit -m "docs: define epics in builds/<name>"
  Tell the user: "Epics defined in `kyros-agent-workflow/builds/<name>/epic-specs/`. When you're ready to start building, run `/execute-plan kyros-agent-workflow/builds/<name>` or `/execute-plan-autonomously kyros-agent-workflow/builds/<name>`."
  ```

**Step 2: Commit**

```bash
git add skills/define-epics/SKILL.md
git commit -m "refactor: update define-epics to use builds/<name>/epic-specs/ structure"
```

---

### Task 4: Update `skills/plan-epic/SKILL.md`

**Files:**
- Modify: `skills/plan-epic/SKILL.md`

The plan-epic skill needs to:
1. Accept `build_dir` instead of `epics_dir`
2. Read epic specs from `<build_dir>/epic-specs/`
3. Write plans to `<build_dir>/plans/` instead of `kyros-agent-workflow/docs/plans/`

**Step 1: Update the skill**

Changes:
- **Context section** (line 12-17): Rename `epics_dir` → `build_dir`, add note that epic specs are in `<build_dir>/epic-specs/`:

  Old:
  ```
  - **epic_spec_path**: Path to the epic's YAML spec file
  - **epics_dir**: Path to the epics directory (for state updates)
  - **epic_name**: Name identifier for this epic
  ```

  New:
  ```
  - **epic_spec_path**: Path to the epic's YAML spec file (in `<build_dir>/epic-specs/`)
  - **build_dir**: Path to the build directory (e.g., `kyros-agent-workflow/builds/v1`)
  - **epic_name**: Name identifier for this epic
  ```

- **Step 6** (line 76-77): Change plan output path:

  Old:
  ```
  Create `kyros-agent-workflow/docs/plans/<epic-name>-plan.md`
  ```

  New:
  ```
  Create `<build_dir>/plans/<epic-name>-plan.md`
  ```

- **Step 7** (line 125-132): Update commit and git add paths:

  Old:
  ```bash
  git add kyros-agent-workflow/tests/ kyros-agent-workflow/docs/plans/
  git commit -m "test: write TDD tests for epic <name>; plan: add implementation plan"
  ```

  New:
  ```bash
  git add kyros-agent-workflow/tests/ <build_dir>/plans/
  git commit -m "test: write TDD tests for epic <name>; plan: add implementation plan"
  ```

**Step 2: Commit**

```bash
git add skills/plan-epic/SKILL.md
git commit -m "refactor: update plan-epic to write plans to <build_dir>/plans/"
```

---

### Task 5: Update `skills/execute-plan/SKILL.md`

**Files:**
- Modify: `skills/execute-plan/SKILL.md`

Rename `epics_dir` to `build_dir` throughout. Update epic spec lookup to search `<build_dir>/epic-specs/`. Update plan path references.

**Step 1: Update the skill**

Key changes:
- **Parameters** (line 15-16): `epics_dir` → `build_dir`
- **Step 1** (line 20-23): Ask for build directory, verify `<build_dir>/epic-specs/` contains `.yaml` files (not `<build_dir>/*.yaml`)
- **Step 5** (line 75-107): `.execution-state.yaml` and `claude-progress.txt` stay in `<build_dir>/` root (no change to relative location, just variable name)
- **Step 5** (line 94): Read `.yaml` files from `<build_dir>/epic-specs/` instead of `<build_dir>/`
- **Phase A** (line 119-131): epic_spec_path becomes `<build_dir>/epic-specs/<epic-file>`, rename `epics_dir` → `build_dir`
- **Phase B** (line 135-148): plan_path becomes `<build_dir>/plans/<epic-name>-plan.md`, rename `epics_dir` → `build_dir`
- **Phase C** (line 152-180): rename `epics_dir` → `build_dir`
- All remaining `<epics_dir>` references → `<build_dir>`

**Step 2: Commit**

```bash
git add skills/execute-plan/SKILL.md
git commit -m "refactor: update execute-plan to use build_dir with epic-specs/ and plans/ subdirs"
```

---

### Task 6: Update `skills/build-step/SKILL.md`

**Files:**
- Modify: `skills/build-step/SKILL.md`

Rename `epics_dir` to `build_dir` throughout. Update plan_path reference.

**Step 1: Update the skill**

Key changes:
- **Context section** (line 14-20): Rename `epics_dir` → `build_dir`, update plan_path example:

  Old:
  ```
  - **plan_path**: Path to the implementation plan (`kyros-agent-workflow/docs/plans/<epic>-plan.md`)
  ```

  New:
  ```
  - **plan_path**: Path to the implementation plan (`<build_dir>/plans/<epic>-plan.md`)
  ```

- All function calls: `epics_dir` → `build_dir` (lines 34, 54, 152, 153, 157, 193, 254, 263)

**Step 2: Commit**

```bash
git add skills/build-step/SKILL.md
git commit -m "refactor: rename epics_dir to build_dir in build-step skill"
```

---

### Task 7: Update `skills/submit-epic/SKILL.md`

**Files:**
- Modify: `skills/submit-epic/SKILL.md`

Rename `epics_dir` to `build_dir` throughout.

**Step 1: Update the skill**

Key changes:
- **Context section** (line 16): `epics_dir` → `build_dir`
- **Step 1** (line 26): `<epics_dir>` → `<build_dir>`
- **Step 3** (line 56): `<epics_dir>` → `<build_dir>`
- **Step 4** (line 61): `<epics_dir>` → `<build_dir>`

**Step 2: Commit**

```bash
git add skills/submit-epic/SKILL.md
git commit -m "refactor: rename epics_dir to build_dir in submit-epic skill"
```

---

### Task 8: Update command entry points

**Files:**
- Modify: `commands/execute-plan.md`
- Modify: `commands/execute-plan-autonomously.md`
- Modify: `commands/status.md`

**Step 1: Update execute-plan commands**

In both `commands/execute-plan.md` and `commands/execute-plan-autonomously.md`, rename the parameter:

Old:
```
- **epics_dir:** The first argument from the user (if provided). If not provided, the skill will ask for it.
```

New:
```
- **build_dir:** The first argument from the user (if provided). If not provided, the skill will ask for it.
```

**Step 2: Update status command**

In `commands/status.md`, update step 4 to look for builds:

Old (line 14):
```
4. **Check for epic directories:** Look for directories containing `.yaml` epic spec files. List any found.
```

New:
```
4. **Check for build directories:** Look for `kyros-agent-workflow/builds/*/epic-specs/` directories containing `.yaml` epic spec files. List any found.
```

Also update the command examples at line 28-29:
```
- `/execute-plan <build-dir>` — Execute epics interactively
- `/execute-plan-autonomously <build-dir>` — Execute epics autonomously
```

**Step 3: Commit**

```bash
git add commands/execute-plan.md commands/execute-plan-autonomously.md commands/status.md
git commit -m "refactor: update commands to use build_dir terminology"
```

---

### Task 9: Update `hooks/definition-of-done.sh`

**Files:**
- Modify: `hooks/definition-of-done.sh`

Rename the variable and usage comment.

**Step 1: Update the hook**

Changes:
- Line 4: `<epics-dir>` → `<build-dir>`
- Line 15: `EPICS_DIR` → `BUILD_DIR`, usage message updated
- Line 20-23: `EPICS_DIR` → `BUILD_DIR`
- Line 50: `EPICS_DIR` → `BUILD_DIR`

**Step 2: Run tests**

Run: `cd /home/kyrosadmin/repos/one_shot_build && npx bats tests/state_test.bats`
Expected: All tests still pass

**Step 3: Commit**

```bash
git add hooks/definition-of-done.sh
git commit -m "refactor: rename EPICS_DIR to BUILD_DIR in definition-of-done hook"
```

---

### Task 10: Final verification

**Step 1: Grep for any remaining old references**

Search for any remaining `epics_dir` or `epics-dir` or `<epics_dir>` references in skills/, commands/, hooks/, lib/, and tests/:

```bash
grep -rn "epics_dir\|epics-dir\|epics.dir" skills/ commands/ hooks/ lib/ tests/ --include="*.md" --include="*.sh" --include="*.bats"
```

Expected: No results (all renamed)

Also verify no remaining hardcoded `kyros-agent-workflow/docs/plans` references in active code:

```bash
grep -rn "kyros-agent-workflow/docs/plans" skills/ commands/ hooks/ lib/ tests/
```

Expected: No results

**Step 2: Run all tests**

Run: `cd /home/kyrosadmin/repos/one_shot_build && npx bats tests/state_test.bats`
Expected: All tests pass

**Step 3: Commit (if any stragglers found)**

```bash
git add -A
git commit -m "refactor: clean up remaining old directory references"
```
