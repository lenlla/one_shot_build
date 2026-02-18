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
    # Create a minimal state file
    cat > "$TEST_DIR/kyros-agent-workflow/project-state.yaml" <<'YAML'
workflow:
  current_phase: "gather_context"
  current_epic: ""
  current_step: ""
YAML

    cd "$TEST_DIR"
    run bash "${SCRIPT_DIR}/session-start.sh"
    assert_success

    # Should be valid JSON (check for hookSpecificOutput key)
    assert_output --partial "hookSpecificOutput"
}

@test "session-start includes current phase in output" {
    cat > "$TEST_DIR/kyros-agent-workflow/project-state.yaml" <<'YAML'
workflow:
  current_phase: "build"
  current_epic: "01-data-loading"
  current_step: "step-02-schema"
YAML

    cd "$TEST_DIR"
    run bash "${SCRIPT_DIR}/session-start.sh"
    assert_success
    assert_output --partial "build"
    assert_output --partial "01-data-loading"
}

@test "session-start handles missing state file gracefully" {
    cd "$TEST_DIR"
    run bash "${SCRIPT_DIR}/session-start.sh"
    assert_success
    assert_output --partial "hookSpecificOutput"
    assert_output --partial "No project-state.yaml found"
}
