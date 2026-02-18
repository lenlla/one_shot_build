#!/usr/bin/env bats
# tests/session_start_test.bats

setup() {
    load "${BATS_TEST_DIRNAME}/../node_modules/bats-support/load"
    load "${BATS_TEST_DIRNAME}/../node_modules/bats-assert/load"

    TEST_DIR="$(mktemp -d)"
    export PROJECT_ROOT="$TEST_DIR"

    # Create the harness directory structure
    mkdir -p "$TEST_DIR/kyros-agent-workflow"

    SCRIPT_DIR="${BATS_TEST_DIRNAME}/../hooks"
}

teardown() {
    rm -rf "$TEST_DIR"
}

@test "session-start outputs valid JSON" {
    cd "$TEST_DIR"
    run bash "${SCRIPT_DIR}/session-start.sh"
    assert_success
    assert_output --partial "hookSpecificOutput"
}

@test "session-start shows active execution when state exists" {
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
started_at: "2026-02-18T14:30:00Z"
mode: interactive
epics:
  data-loading:
    status: building
    current_step: 2
    steps_total: 4
YAML

    cd "$TEST_DIR"
    run bash "${SCRIPT_DIR}/session-start.sh"
    assert_success
    assert_output --partial "Active execution"
    assert_output --partial "epics/v1"
}

@test "session-start handles no execution states gracefully" {
    cd "$TEST_DIR"
    run bash "${SCRIPT_DIR}/session-start.sh"
    assert_success
    assert_output --partial "hookSpecificOutput"
    assert_output --partial "No active executions"
}

@test "session-start lists multiple active executions" {
    mkdir -p "$TEST_DIR/epics/v1" "$TEST_DIR/epics/v2"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: building
YAML
    cat > "$TEST_DIR/epics/v2/.execution-state.yaml" <<'YAML'
epics:
  transform:
    status: planning
YAML

    cd "$TEST_DIR"
    run bash "${SCRIPT_DIR}/session-start.sh"
    assert_success
    assert_output --partial "Active executions"
    assert_output --partial "epics/v1"
    assert_output --partial "epics/v2"
}
