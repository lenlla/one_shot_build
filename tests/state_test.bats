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

@test "log_progress appends to claude-progress.txt in epics dir" {
    mkdir -p "$TEST_DIR/epics/v1"
    run log_progress "$TEST_DIR/epics/v1" "Completed step-01 implementation"
    assert_success

    run cat "$TEST_DIR/epics/v1/claude-progress.txt"
    assert_output --partial "Completed step-01 implementation"
}

@test "log_progress includes timestamp" {
    mkdir -p "$TEST_DIR/epics/v1"
    run log_progress "$TEST_DIR/epics/v1" "Test message"
    assert_success

    run cat "$TEST_DIR/epics/v1/claude-progress.txt"
    # Should contain ISO-like timestamp
    assert_output --regexp "[0-9]{4}-[0-9]{2}-[0-9]{2}"
}

# --- execution state tests ---

@test "execution_state_file returns correct path" {
    run execution_state_file "/tmp/epics/v1"
    assert_success
    assert_output "/tmp/epics/v1/.execution-state.yaml"
}

@test "read_execution_state returns empty when no file exists" {
    run read_execution_state "/tmp/nonexistent" "epics.test.status"
    assert_success
    assert_output ""
}

@test "read_execution_state reads epic status" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
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
    run read_execution_state "$TEST_DIR/epics/v1" "epics.data-loading.status"
    assert_success
    assert_output "completed"
}

@test "update_execution_state writes epic status" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: pending
YAML
    run update_execution_state "$TEST_DIR/epics/v1" "epics.data-loading.status" "building"
    assert_success

    run read_execution_state "$TEST_DIR/epics/v1" "epics.data-loading.status"
    assert_output "building"
}

@test "find_execution_states finds state files in project" {
    mkdir -p "$TEST_DIR/epics/v1" "$TEST_DIR/epics/v2"
    echo "epics: {}" > "$TEST_DIR/epics/v1/.execution-state.yaml"
    echo "epics: {}" > "$TEST_DIR/epics/v2/.execution-state.yaml"

    run find_execution_states
    assert_success
    assert_output --partial "epics/v1/.execution-state.yaml"
    assert_output --partial "epics/v2/.execution-state.yaml"
}

@test "find_active_executions only returns dirs with incomplete epics" {
    mkdir -p "$TEST_DIR/epics/v1" "$TEST_DIR/epics/v2"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: completed
YAML
    cat > "$TEST_DIR/epics/v2/.execution-state.yaml" <<'YAML'
epics:
  transform:
    status: building
YAML

    run find_active_executions
    assert_success
    assert_output --partial "epics/v2"
    refute_output --partial "epics/v1"
}

@test "execution_summary shows progress" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
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

    run execution_summary "$TEST_DIR/epics/v1"
    assert_success
    assert_output --partial "1/3 epics done"
    assert_output --partial "transformation"
}
