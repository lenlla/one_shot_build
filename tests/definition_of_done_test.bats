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
    echo "Epic build progress logged" > "$TEST_DIR/kyros-agent-workflow/claude-progress.txt"

    # Create epics directory with execution state
    mkdir -p "$TEST_DIR/epics/v1"
    cat > "$TEST_DIR/epics/v1/.execution-state.yaml" <<'YAML'
epics:
  data-loading:
    status: submitting
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
    run bash "$SCRIPT" "$TEST_DIR/epics/v1" "data-loading"
    assert_success
    assert_output --partial "PASS"
}

@test "fails when TODO comments found in src" {
    echo '# TODO: fix this later' > "$TEST_DIR/kyros-agent-workflow/src/main.py"
    git -C "$TEST_DIR" add -A
    git -C "$TEST_DIR" commit -q -m "add src"

    run bash "$SCRIPT" "$TEST_DIR/epics/v1" "data-loading"
    assert_failure
    assert_output --partial "TODO"
}

@test "fails when uncommitted changes exist" {
    echo 'new file' > "$TEST_DIR/kyros-agent-workflow/src/new.py"

    run bash "$SCRIPT" "$TEST_DIR/epics/v1" "data-loading"
    assert_failure
    assert_output --partial "Uncommitted"
}

@test "fails when progress file is empty" {
    > "$TEST_DIR/kyros-agent-workflow/claude-progress.txt"
    git -C "$TEST_DIR" add -A
    git -C "$TEST_DIR" commit -q -m "empty progress"

    run bash "$SCRIPT" "$TEST_DIR/epics/v1" "data-loading"
    assert_failure
    assert_output --partial "claude-progress.txt"
}
