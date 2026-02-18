#!/usr/bin/env bats
# tests/definition_of_done_test.bats

setup() {
    load "${BATS_TEST_DIRNAME}/../node_modules/bats-support/load"
    load "${BATS_TEST_DIRNAME}/../node_modules/bats-assert/load"

    TEST_DIR="$(mktemp -d)"
    export PROJECT_ROOT="$TEST_DIR"

    SCRIPT="${BATS_TEST_DIRNAME}/../hooks/definition-of-done.sh"

    # Create minimal project structure
    mkdir -p "$TEST_DIR/kyros-agent-workflow/tests" "$TEST_DIR/kyros-agent-workflow/src"
    echo "" > "$TEST_DIR/kyros-agent-workflow/claude-progress.txt"

    # Create state file with completed steps
    cat > "$TEST_DIR/kyros-agent-workflow/project-state.yaml" <<'YAML'
workflow:
  current_phase: "submit"
  current_epic: "01-data-loading"
epics:
  01-data-loading:
    status: in_progress
    steps:
      step-01:
        status: completed
        tests_pass: true
        review_approved: true
YAML

    cd "$TEST_DIR"
    git init -q
    git config user.email "test@test.com"
    git config user.name "Test"
    git add -A
    git commit -q -m "initial"
}

teardown() {
    rm -rf "$TEST_DIR"
}

@test "passes when all DoD criteria are met" {
    run bash "$SCRIPT"
    assert_success
    assert_output --partial "PASS"
}

@test "fails when state file has unapproved steps" {
    cat > "$TEST_DIR/kyros-agent-workflow/project-state.yaml" <<'YAML'
workflow:
  current_phase: "submit"
  current_epic: "01-data-loading"
epics:
  01-data-loading:
    status: in_progress
    steps:
      step-01:
        status: completed
        tests_pass: true
        review_approved: false
YAML

    run bash "$SCRIPT"
    assert_failure
    assert_output --partial "review_approved"
}

@test "fails when TODO comments found in src" {
    echo '# TODO: fix this later' > "$TEST_DIR/kyros-agent-workflow/src/main.py"
    git -C "$TEST_DIR" add -A
    git -C "$TEST_DIR" commit -q -m "add src"

    run bash "$SCRIPT"
    assert_failure
    assert_output --partial "TODO"
}
