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

# --- read_state tests ---

@test "read_state returns empty string when no state file exists" {
    run read_state "workflow.current_phase"
    assert_success
    assert_output ""
}

@test "read_state reads current phase from state file" {
    cat > "$PROJECT_ROOT/kyros-agent-workflow/project-state.yaml" <<'YAML'
project:
  name: "Test Project"
workflow:
  current_phase: "gather_context"
  current_epic: ""
  current_step: ""
YAML
    run read_state "workflow.current_phase"
    assert_success
    assert_output "gather_context"
}

@test "read_state reads nested epic status" {
    cat > "$PROJECT_ROOT/kyros-agent-workflow/project-state.yaml" <<'YAML'
project:
  name: "Test Project"
workflow:
  current_phase: "build"
  current_epic: "01-data-loading"
epics:
  01-data-loading:
    status: in_progress
YAML
    run read_state "epics.01-data-loading.status"
    assert_success
    assert_output "in_progress"
}

# --- update_state tests ---

@test "update_state sets a value in the state file" {
    cat > "$PROJECT_ROOT/kyros-agent-workflow/project-state.yaml" <<'YAML'
workflow:
  current_phase: "gather_context"
YAML
    run update_state "workflow.current_phase" "define_epics"
    assert_success

    run read_state "workflow.current_phase"
    assert_output "define_epics"
}

# --- get_current_phase tests ---

@test "get_current_phase returns the current workflow phase" {
    cat > "$PROJECT_ROOT/kyros-agent-workflow/project-state.yaml" <<'YAML'
workflow:
  current_phase: "build"
YAML
    run get_current_phase
    assert_success
    assert_output "build"
}

# --- get_current_epic tests ---

@test "get_current_epic returns the current epic" {
    cat > "$PROJECT_ROOT/kyros-agent-workflow/project-state.yaml" <<'YAML'
workflow:
  current_epic: "02-data-translation"
YAML
    run get_current_epic
    assert_success
    assert_output "02-data-translation"
}

# --- get_current_step tests ---

@test "get_current_step returns the current step" {
    cat > "$PROJECT_ROOT/kyros-agent-workflow/project-state.yaml" <<'YAML'
workflow:
  current_step: "step-03-type-casting"
YAML
    run get_current_step
    assert_success
    assert_output "step-03-type-casting"
}

# --- log_progress tests ---

@test "log_progress appends to claude-progress.txt" {
    run log_progress "Completed step-01 implementation"
    assert_success

    run cat "$PROJECT_ROOT/kyros-agent-workflow/claude-progress.txt"
    assert_output --partial "Completed step-01 implementation"
}

@test "log_progress includes timestamp" {
    run log_progress "Test message"
    assert_success

    run cat "$PROJECT_ROOT/kyros-agent-workflow/claude-progress.txt"
    # Should contain ISO-like timestamp
    assert_output --regexp "[0-9]{4}-[0-9]{2}-[0-9]{2}"
}
