# Integration Multi-Turn Refactor Design

**Status:** Proposed  
**Date:** 2026-02-28

## Goal

Restore strict behavioral validation for integration tests that were relaxed during stabilization by replacing emulated interactive execution with deterministic multi-turn Claude Code execution.

Target behavior:
- Use `claude -p` + `--continue` across turns
- Parse `--output-format stream-json` logs for tool/skill evidence
- Assert strict workflow outcomes (not just artifact existence)

## Problem Summary

Current `ClaudeRunner.run_interactive()` emulates interactivity via a single `--print` call. This made the suite stable but weakened validation:

- `test_define_epics_structural` can skip when no epics are persisted
- `test_resume_after_interrupt` no longer verifies actual interruption/resume lifecycle
- `test_circuit_breakers` only checks that status exists, not breaker correctness

## Non-Goals

- No return to a single long-lived piped interactive subprocess for tests
- No PTY event loop in this phase
- No broad test redesign outside the relaxed tests and shared runner

## Design Overview

### 1. Turn Runner (new)

Create `integration_tests/turn_runner.py` as a deterministic turn executor.

Responsibilities:
- Execute one turn via subprocess:
  - `claude -p <prompt> [--continue] --plugin-dir <repo> --dangerously-skip-permissions --max-turns N --output-format stream-json`
- Capture raw output to a per-turn log file
- Parse stream-json lines into structured events
- Return a `TurnResult` object with:
  - prompt, command, exit code, timeout flag
  - raw log path
  - parsed assistant texts
  - parsed `tool_use` events
  - parsed skill/tool names and order

Constraints:
- One Claude process per turn
- Same working directory across turns for continuity
- Explicit turn caps (`--max-turns`) per phase

### 2. Playbook Contract (new)

Create `integration_tests/playbooks.py` with deterministic turn scripts.

Each playbook provides:
- `name`
- ordered `turns`: prompt template + max_turns + assertions for the turn
- stop condition(s)
- failure diagnostics to emit on mismatch

No realtime prompt detection. Conversation advances only when prior turn exits and validations pass.

### 3. Shared Parsing Helpers (new)

Create parser helpers for stream-json logs:
- extract assistant text chunks
- extract tool use events (`Skill`, `Task`, `TodoWrite`, etc.)
- detect invoked skill names
- detect ordering (e.g., first `Skill` before non-planning tools)

### 4. Test Migration Scope

#### A) `test_define_epics_structural`

Current issue: skip when epics directory not materialized.

Refactor:
- Turn 1: request `/define-epics ...`
- Turn 2: explicit approval message (for example: "yes, save these epics now to kyros-agent-workflow/builds/v1/epic-specs")
- Assertions:
  - no skip path
  - epics directory exists
  - at least 2 valid YAML specs exist
  - expected numbering/schema checks still pass

#### B) `test_resume_after_interrupt`

Current issue: seeded state compatibility check only.

Refactor:
- Start execution for one bounded turn so state is initialized
- Simulate interruption by ending turn before full completion (via low max turns / explicit stop point)
- Resume with `--continue`
- Assertions:
  - pre-resume state exists
  - post-resume run references existing execution context
  - state progression is monotonic (not reset to fresh initialization)

#### C) `test_circuit_breakers`

Current issue: status non-empty check only.

Refactor:
- Run induced failure scenarios with low thresholds
- Continue through bounded turns until terminal or timeout
- Assertions per scenario:
  - terminal safeguarded status (blocked/failed by breaker) OR explicit breaker reason evidence
  - not a false success for scenarios designed to be unsatisfiable
  - if timeout occurs, test fails with log evidence (not silently passing)

## Data and Log Layout

Per test run:
- `integration_tests/.logs/<test_name>/turn-01.json`
- `integration_tests/.logs/<test_name>/turn-02.json`
- ...

Optional summary artifact:
- `integration_tests/.reports/<test_name>-summary.json`

## Assertion Strategy

Each migrated test must assert all layers:

1. **Conversation evidence** (stream-json)
- required tools/skills invoked
- expected ordering where relevant

2. **State evidence**
- `.execution-state.yaml` existence and valid transitions

3. **Artifact evidence**
- epics/tests/code files created as expected

A test passes only when all required layers pass.

## Backward Compatibility

- Keep `ClaudeRunner.run_print()` for existing simple tests.
- Deprecate `run_interactive()` and migrate callers to turn runner.
- During migration window, allow both mechanisms to coexist.

## CI Implications

- `ci-fast`: unchanged deterministic baseline
- `ci-multiturn-critical`: migrate to new strict turn-runner tests for selected cases
- `ci-multiturn-full`: full integration suite with strict assertions once migrations complete

## Risks and Mitigations

1. Model nondeterminism across turns
- Mitigation: strict but prompt-anchored playbooks and bounded turn counts

2. Long runtime
- Mitigation: critical subset on PR, full suite nightly/manual

3. Parsing drift with CLI output changes
- Mitigation: central parser module and fixture-based parser tests

## Success Criteria

1. `test_define_epics_structural` has no skip fallback and passes reliably via multi-turn continuation.
2. `test_resume_after_interrupt` validates real continuation semantics, not seeded-state-only behavior.
3. `test_circuit_breakers` enforces breaker outcomes (or explicit failure) instead of non-empty status.
4. Multi-turn critical lane is stable enough for PR gating.

## Implementation Order

1. Add `turn_runner.py` + parser helpers + unit tests for parser
2. Migrate `test_define_epics_structural`
3. Migrate `test_resume_after_interrupt`
4. Migrate `test_circuit_breakers`
5. Remove relaxed/skip pathways introduced during stabilization
