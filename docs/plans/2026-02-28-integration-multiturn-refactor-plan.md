# Integration Multi-Turn Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace relaxed integration-test behavior with strict multi-turn validation using turn-by-turn Claude CLI execution (`claude -p` + `--continue`) and stream-json assertions.

**Design doc:** `docs/plans/2026-02-28-integration-multiturn-refactor-design.md`

**Success criteria:**
- `test_define_epics_structural` no longer skips when epics are not materialized in non-interactive mode.
- `test_resume_after_interrupt` verifies real continuation semantics across turns.
- `test_circuit_breakers` verifies strict breaker outcomes or fails with explicit diagnostics.
- `ci-multiturn-critical` runs strict subset reliably.

---

## Task 1: Build Shared Turn Runner

**Files:**
- Create: `integration_tests/turn_runner.py`
- Create: `integration_tests/test_turn_runner.py`

**Step 1: Create runner API and data model**

Implement `run_turn(...)` with:
- `prompt: str`
- `working_dir: Path`
- `plugin_dir: Path`
- `continue_session: bool = False`
- `max_turns: int = 3`
- `timeout: int = 300`
- `log_path: Path | None = None`

Return `TurnResult` dataclass containing:
- prompt, command, exit_code, timed_out
- `log_path`
- parsed assistant text list
- parsed tool events list
- parsed skill names list

**Step 2: Execute one process per turn**

Command shape:

```bash
claude -p "<prompt>" \
  [--continue] \
  --plugin-dir "<plugin_dir>" \
  --dangerously-skip-permissions \
  --max-turns "<N>" \
  --output-format stream-json
```

**Step 3: Add parser helpers**

Add parser functions for stream-json lines:
- assistant message extraction
- tool-use extraction
- skill invocation extraction
- first-skill index and pre-skill tool invocations

**Step 4: Add runner unit tests**

In `test_turn_runner.py`, test parser behavior with fixture lines:
- detects skill invocation
- detects tool order
- handles malformed lines safely

**Verification:**

```bash
python3 -m pytest integration_tests/test_turn_runner.py -q
```

---

## Task 2: Add Multi-Turn Playbooks

**Files:**
- Create: `integration_tests/playbooks.py`
- Create: `integration_tests/test_playbooks.py`

**Step 1: Define playbook schema**

Create lightweight structures:
- `TurnSpec` (prompt template, max_turns, required signals)
- `Playbook` (name, ordered turns, stop conditions)

**Step 2: Implement initial playbooks**

Add:
- `define_epics_playbook`
- `resume_playbook`
- `circuit_breaker_playbook`

Keep prompts deterministic and explicit for approvals/continuation.

**Step 3: Add playbook tests**

Verify prompt rendering and turn counts/required fields.

**Verification:**

```bash
python3 -m pytest integration_tests/test_playbooks.py -q
```

---

## Task 3: Refactor Define-Epics Structural Test to Strict Multi-Turn

**Files:**
- Modify: `integration_tests/test_define_epics.py`

**Step 1: Replace `run_interactive()` usage**

Use turn runner + playbook:
- Turn 1: request define-epics generation
- Turn 2: explicit approval to persist epic specs

**Step 2: Remove skip fallback**

Delete non-interactive skip path and enforce strict persistence.

**Step 3: Strengthen assertions**

Require:
- epics directory exists
- >=2 YAML files
- YAML parses

**Verification:**

```bash
python3 -m pytest integration_tests/test_define_epics.py::test_define_epics_structural -q
```

---

## Task 4: Refactor Resume Test to True Continuation Semantics

**Files:**
- Modify: `integration_tests/test_resume_recovery.py`

**Step 1: Remove seeded-state-only path**

Start execution via turn runner with bounded turn count so run is partial.

**Step 2: Resume with `--continue`**

Run resume turn and assert conversation/state indicate continuation, not fresh init.

**Step 3: Add strict state progression checks**

Assert that:
- existing state was detected
- state transitions forward across resume turn
- no full reset to initial status

**Verification:**

```bash
python3 -m pytest integration_tests/test_resume_recovery.py::test_resume_after_interrupt -q
```

---

## Task 5: Refactor Circuit Breaker Tests Back to Strict Outcomes

**Files:**
- Modify: `integration_tests/test_circuit_breakers.py`

**Step 1: Replace relaxed non-empty status assertions**

Enforce scenario-specific expected outcomes:
- no-progress scenario should halt/terminal-break
- repeated-error scenario should halt/terminal-break
- review-rounds scenario should halt/terminal-break

**Step 2: Add bounded continuation loop**

Use fixed max turns and fail if no terminal status reached.

**Step 3: Add diagnostics on failure**

Include:
- last assistant text excerpt
- last known epic status
- relevant tool events from logs

**Verification:**

```bash
python3 -m pytest integration_tests/test_circuit_breakers.py -q
```

---

## Task 6: Tighten Shared Structural Assertions

**Files:**
- Modify: `integration_tests/assertions/structural.py`

**Step 1: Revisit `check_profile_data` contract**

Decide if `analyst-notes.md` is required. If required by product behavior, enforce again.

**Step 2: Keep only real path compatibility changes**

Preserve legitimate state-file path compatibility for builds/v1.

**Verification:**

```bash
python3 -m pytest integration_tests/assertions/test_structural.py -q
```

---

## Task 7: Migrate Critical Lane to Strict Tests

**Files:**
- Modify: `scripts/test-multiturn-critical.sh`
- Optionally modify: `.github/workflows/ci-multiturn-critical.yml`

**Step 1: Ensure script runs strict restored subset**

Include:
- define-epics structural strict test
- resume strict test
- selected circuit-breaker strict test(s)

**Step 2: Validate runner assumptions**

Keep self-hosted + `claude` prerequisite checks.

**Verification:**

```bash
./scripts/test-multiturn-critical.sh
```

---

## Task 8: End-to-End Validation

**Files:**
- No new files required

**Step 1: Run full integration suite**

```bash
python3 -m pytest integration_tests -q
```

**Step 2: Run fast lane to confirm no regressions**

```bash
npm run test:fast
```

**Step 3: Record residual flakes and mitigation notes**

If flaky, document exact tests and add bounded retry strategy where justified.

---

## Task 9: Complete Structural Migration Consistency

**Files:**
- Modify: `integration_tests/test_*.py` (only structural tests still using `ClaudeRunner.run_interactive`)
- Modify: `integration_tests/playbooks.py` (only if new deterministic turns are needed)

**Step 1: Inventory structural tests still using interactive runner**

Run:

```bash
rg -n "run_interactive\(" integration_tests/test_*.py
```

Filter to structural tests only.

**Step 2: Migrate one structural test at a time**

For a single structural test:
- replace `run_interactive` with `run_turn(...)`
- add bounded `--continue` loop
- keep strict assertions; no skip fallback
- include diagnostics with last log path on failure

**Step 3: Add/update deterministic playbook turn specs**

If the test needs dedicated prompts, add minimal deterministic turns in `playbooks.py`.

**Step 4: Verify the single migrated test**

Run:

```bash
python3 -m pytest <exact_test_node> -q
```

**Step 5: Commit single-test migration**

```bash
git add <modified test file(s)> integration_tests/playbooks.py
git commit -m "test: migrate <test-name> structural flow to turn runner"
```

**Step 6: Repeat Steps 2-5 until inventory is clean**

Re-run inventory command and ensure no structural tests remain on `run_interactive`.

**Step 7: Verify structural subset end-to-end**

Run:

```bash
python3 -m pytest integration_tests/test_* -q -k structural
```

**Step 8: Commit structural consistency sweep**

```bash
git add integration_tests
git commit -m "test: complete structural turn-runner migration consistency"
```

**Verification:**

```bash
rg -n "run_interactive\(" integration_tests/test_*.py
python3 -m pytest integration_tests/test_* -q -k structural
```

---

## Task 10: Add Fast Deterministic Harness-Artifact Test

**Files:**
- Create: `integration_tests/test_execute_plan_artifacts_fast.py`
- Modify: `scripts/test-fast.sh`
- Modify: `package.json` (if needed for lane inclusion)
- Optionally modify: `integration_tests/assertions/structural.py` (reuse helpers only)

**Step 1: Define deterministic fixture setup**

Use local fixture setup (no long interactive run) that produces:
- `.execution-state.yaml`
- branches `epic/<name>`
- tags `tdd-baseline-<name>`

**Step 2: Write failing fast artifact test**

Create assertions for:
- execution state file exists and parses
- expected state progression shape keys exist
- branch/tag naming conventions are present

**Step 3: Run test to confirm failure (red)**

```bash
python3 -m pytest integration_tests/test_execute_plan_artifacts_fast.py -q
```

**Step 4: Implement minimal setup/helpers to make test pass**

Keep runtime short and deterministic; avoid full multi-turn execution.

**Step 5: Re-run test until passing (green)**

```bash
python3 -m pytest integration_tests/test_execute_plan_artifacts_fast.py -q
```

**Step 6: Integrate test into fast lane**

Include this test in `test-fast` so regressions surface quickly.

**Step 7: Re-run fast lane**

```bash
npm run test:fast
```

**Step 8: Document intent**

Add short comment/doc note clarifying this is a fast orchestration contract test, not full behavioral coverage.

**Step 9: Commit fast artifact coverage**

```bash
git add integration_tests/test_execute_plan_artifacts_fast.py scripts/test-fast.sh package.json
git commit -m "test: add fast deterministic execute-plan artifact checks"
```

**Verification:**

```bash
python3 -m pytest integration_tests/test_execute_plan_artifacts_fast.py -q
npm run test:fast
```

---

## Task 11: Add Flake Telemetry and Drift Guards

**Files:**
- Create: `integration_tests/metrics.py` (or similar helper)
- Create: `scripts/check-flake-drift.py` (or equivalent)
- Modify: `scripts/test-multiturn-critical.sh`
- Modify: `scripts/test-multiturn-full.sh`
- Optionally modify: `.github/workflows/ci-multiturn-critical.yml`
- Optionally modify: `.github/workflows/ci-multiturn-full.yml`

**Step 1: Define metrics schema**

Create JSONL schema with:
- test name
- duration seconds
- continuation/retry count
- pass/fail
- coarse failure reason bucket (timeout/assertion/etc.)

**Step 2: Add metrics emit helper**

Implement helper to append one JSON record per test execution.

**Step 3: Wire metrics collection into lane scripts**

Update `test-multiturn-critical.sh` and `test-multiturn-full.sh` to write metrics files every run.

**Step 4: Verify local metrics output**

Run:

```bash
./scripts/test-multiturn-critical.sh
```

Confirm JSONL file exists and contains expected fields.

**Step 5: Persist CI artifacts**

Upload metrics files from critical/full lanes.

**Step 6: Add drift checker**

Add a checker script that compares recent runs and flags sustained drift (not single-run spikes), for example:
- duration median exceeds threshold for N consecutive runs
- retry count trend exceeds threshold
- failure rate over rolling window exceeds threshold

**Step 7: Start in warning-only mode**

Emit non-blocking warnings in CI with clear thresholds in logs.

**Step 8: Promote to blocking mode after calibration**

After stable threshold tuning, enable blocking behavior in CI.

**Step 9: Commit telemetry and drift guards**

```bash
git add integration_tests/metrics.py scripts/check-flake-drift.py scripts/test-multiturn-critical.sh scripts/test-multiturn-full.sh .github/workflows/ci-multiturn-critical.yml .github/workflows/ci-multiturn-full.yml
git commit -m "ci: add integration flake telemetry and drift guards"
```

**Verification:**

```bash
./scripts/test-multiturn-critical.sh
./scripts/test-multiturn-full.sh
```

---

## Rollout Notes

- Keep existing CI split (`ci-fast`, `ci-multiturn-critical`, `ci-multiturn-full`).
- Promote additional strict tests into critical lane only after two consecutive stable runs.
- Do not reintroduce `run_interactive` emulation paths into strict tests.
