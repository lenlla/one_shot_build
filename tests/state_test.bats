#!/usr/bin/env bats
# tests/state_test.bats

setup() {
    load "${BATS_TEST_DIRNAME}/../node_modules/bats-support/load"
    load "${BATS_TEST_DIRNAME}/../node_modules/bats-assert/load"

    TEST_DIR="$(mktemp -d)"
    export PROJECT_ROOT="$TEST_DIR"

    # Create the harness directory structure
    mkdir -p "$PROJECT_ROOT/kyros-agent-workflow"

    # Source the library
    source "${BATS_TEST_DIRNAME}/../lib/state.sh"
}

teardown() {
    rm -rf "$TEST_DIR"
}

# --- log_progress tests ---

@test "log_progress appends to claude-progress.txt in build dir" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    run log_progress "$TEST_DIR/kyros-agent-workflow/builds/v1" "Completed step-01 implementation"
    assert_success

    run cat "$TEST_DIR/kyros-agent-workflow/builds/v1/claude-progress.txt"
    assert_output --partial "Completed step-01 implementation"
}

@test "log_progress includes timestamp" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    run log_progress "$TEST_DIR/kyros-agent-workflow/builds/v1" "Test message"
    assert_success

    run cat "$TEST_DIR/kyros-agent-workflow/builds/v1/claude-progress.txt"
    # Should contain ISO-like timestamp
    assert_output --regexp "[0-9]{4}-[0-9]{2}-[0-9]{2}"
}

# --- execution state tests ---

@test "execution_state_file returns correct path" {
    run execution_state_file "/tmp/kyros-agent-workflow/builds/v1"
    assert_success
    assert_output "/tmp/kyros-agent-workflow/builds/v1/.execution-state.yaml"
}

@test "read_execution_state returns empty when no file exists" {
    run read_execution_state "/tmp/nonexistent" "epics.test.status"
    assert_success
    assert_output ""
}

@test "read_execution_state reads epic status" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
started_at: "2026-02-18T14:30:00Z"
mode: interactive
epics:
  data-loading:
    status: completed
  transformation:
    status: building
    current_step: 3
    steps_total: 5
YAML
    run read_execution_state "$TEST_DIR/kyros-agent-workflow/builds/v1" "epics.data-loading.status"
    assert_success
    assert_output "completed"
}

@test "update_execution_state writes epic status" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: pending
YAML
    run update_execution_state "$TEST_DIR/kyros-agent-workflow/builds/v1" "epics.data-loading.status" "building"
    assert_success

    run read_execution_state "$TEST_DIR/kyros-agent-workflow/builds/v1" "epics.data-loading.status"
    assert_output "building"
}

@test "find_execution_states finds state files in project" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1" "$TEST_DIR/kyros-agent-workflow/builds/v2"
    echo "epics: {}" > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml"
    echo "epics: {}" > "$TEST_DIR/kyros-agent-workflow/builds/v2/.execution-state.yaml"

    run find_execution_states
    assert_success
    assert_output --partial "builds/v1/.execution-state.yaml"
    assert_output --partial "builds/v2/.execution-state.yaml"
}

@test "find_active_executions only returns dirs with incomplete epics" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1" "$TEST_DIR/kyros-agent-workflow/builds/v2"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: completed
YAML
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v2/.execution-state.yaml" <<'YAML'
epics:
  transform:
    status: building
YAML

    run find_active_executions
    assert_success
    assert_output --partial "builds/v2"
    refute_output --partial "builds/v1"
}

@test "execution_summary shows progress" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: completed
  transformation:
    status: building
    current_step: 3
    steps_total: 5
  reporting:
    status: pending
YAML

    run execution_summary "$TEST_DIR/kyros-agent-workflow/builds/v1"
    assert_success
    assert_output --partial "1/3 epics done"
    assert_output --partial "transformation"
}

# --- step-level state tests ---

@test "read_step_status returns empty when no steps exist" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
YAML
    run read_step_status "$TEST_DIR/kyros-agent-workflow/builds/v1" "data-loading" "step-01"
    assert_success
    assert_output ""
}

@test "read_step_status returns step status" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    steps:
      step-01:
        status: completed
      step-02:
        status: in_progress
YAML
    run read_step_status "$TEST_DIR/kyros-agent-workflow/builds/v1" "data-loading" "step-01"
    assert_success
    assert_output "completed"
}

@test "update_step_status sets step status" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    steps:
      step-01:
        status: pending
YAML
    run update_step_status "$TEST_DIR/kyros-agent-workflow/builds/v1" "data-loading" "step-01" "in_progress"
    assert_success

    run read_step_status "$TEST_DIR/kyros-agent-workflow/builds/v1" "data-loading" "step-01"
    assert_output "in_progress"
}

@test "init_steps_from_plan creates step entries from plan headings" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
YAML
    # Create a mock plan file in the build's plans directory
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1/plans"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/plans/data-loading-plan.md" <<'PLAN'
# Data Loading Implementation Plan

**Goal:** Load CSV files
**Architecture:** Simple pandas loader

---

### Task 1: Load CSV

**Files:**
- Create: `src/loader.py`

### Task 2: Validate Schema

**Files:**
- Create: `src/validator.py`

### Task 3: Type Casting

**Files:**
- Create: `src/caster.py`
PLAN
    run init_steps_from_plan "$TEST_DIR/kyros-agent-workflow/builds/v1" "data-loading" "$TEST_DIR/kyros-agent-workflow/builds/v1/plans/data-loading-plan.md"
    assert_success

    run read_step_status "$TEST_DIR/kyros-agent-workflow/builds/v1" "data-loading" "task-1-load-csv"
    assert_output "pending"

    run read_step_status "$TEST_DIR/kyros-agent-workflow/builds/v1" "data-loading" "task-2-validate-schema"
    assert_output "pending"

    run read_step_status "$TEST_DIR/kyros-agent-workflow/builds/v1" "data-loading" "task-3-type-casting"
    assert_output "pending"
}

@test "get_next_pending_step returns first non-completed step" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    steps:
      task-1-load-csv:
        status: completed
      task-2-validate-schema:
        status: pending
      task-3-type-casting:
        status: pending
YAML
    run get_next_pending_step "$TEST_DIR/kyros-agent-workflow/builds/v1" "data-loading"
    assert_success
    assert_output "task-2-validate-schema"
}

@test "get_next_pending_step returns empty when all steps completed" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    steps:
      task-1-load-csv:
        status: completed
      task-2-validate-schema:
        status: completed
YAML
    run get_next_pending_step "$TEST_DIR/kyros-agent-workflow/builds/v1" "data-loading"
    assert_success
    assert_output ""
}

@test "increment_review_rounds tracks review count" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    steps:
      step-01:
        status: in_progress
        review_rounds: 1
YAML
    run increment_review_rounds "$TEST_DIR/kyros-agent-workflow/builds/v1" "data-loading" "step-01"
    assert_success

    run read_execution_state "$TEST_DIR/kyros-agent-workflow/builds/v1" 'epics.data-loading.steps.step-01.review_rounds'
    assert_output "2"
}

@test "execution_summary includes step progress" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    current_step: "task-2-validate-schema"
    steps:
      task-1-load-csv:
        status: completed
      task-2-validate-schema:
        status: in_progress
      task-3-type-casting:
        status: pending
YAML

    run execution_summary "$TEST_DIR/kyros-agent-workflow/builds/v1"
    assert_success
    assert_output --partial "step 1/3"
}

@test "serve.sh symlinks state file from specified build dir" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    echo "epics: {}" > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml"

    SERVE_DIR=$(mktemp -d)
    SCRIPT_DIR="${BATS_TEST_DIRNAME}/../dashboard"

    # Simulate what serve.sh does: symlink dashboard files + state file
    ln -s "$SCRIPT_DIR"/* "$SERVE_DIR/" 2>/dev/null || true
    ln -s "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" "$SERVE_DIR/execution-state.yaml" 2>/dev/null || true

    run test -L "$SERVE_DIR/execution-state.yaml"
    assert_success

    run cat "$SERVE_DIR/execution-state.yaml"
    assert_output --partial "epics"

    rm -rf "$SERVE_DIR"
}

@test "update_execution_state can set tests_pass gate field" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    steps:
      task-1-load-csv:
        status: in_progress
YAML
    run update_execution_state "$TEST_DIR/kyros-agent-workflow/builds/v1" 'epics."data-loading".steps."task-1-load-csv".tests_pass' "true"
    assert_success

    run read_execution_state "$TEST_DIR/kyros-agent-workflow/builds/v1" 'epics."data-loading".steps."task-1-load-csv".tests_pass'
    assert_output "true"
}

@test "update_execution_state can set review_approved gate field" {
    mkdir -p "$TEST_DIR/kyros-agent-workflow/builds/v1"
    cat > "$TEST_DIR/kyros-agent-workflow/builds/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
    steps:
      task-1-load-csv:
        status: completed
        tests_pass: true
YAML
    run update_execution_state "$TEST_DIR/kyros-agent-workflow/builds/v1" 'epics."data-loading".steps."task-1-load-csv".review_approved' "true"
    assert_success

    run read_execution_state "$TEST_DIR/kyros-agent-workflow/builds/v1" 'epics."data-loading".steps."task-1-load-csv".review_approved'
    assert_output "true"
}
