#!/usr/bin/env bats
# tests/check_test_immutability_test.bats

setup() {
    load "${BATS_TEST_DIRNAME}/../node_modules/bats-support/load"
    load "${BATS_TEST_DIRNAME}/../node_modules/bats-assert/load"

    TEST_DIR="$(mktemp -d)"
    cd "$TEST_DIR"

    # Initialize a git repo
    git init -q
    git config user.email "test@test.com"
    git config user.name "Test"

    # Create initial test file and commit (simulates TDD phase)
    mkdir -p tests
    echo 'def test_example(): assert True' > tests/test_example.py
    git add tests/test_example.py
    git commit -q -m "test: add tests (TDD phase)"

    # Tag the TDD commit so the script can reference it
    git tag tdd-baseline

    SCRIPT="${BATS_TEST_DIRNAME}/../hooks/check-test-immutability.sh"
}

teardown() {
    rm -rf "$TEST_DIR"
}

@test "passes when test files are unchanged since TDD baseline" {
    # No changes to test files
    run bash "$SCRIPT" tdd-baseline
    assert_success
    assert_output --partial "PASS"
}

@test "fails when a test file is modified during build" {
    # Modify a test file
    echo 'def test_example(): assert False' > tests/test_example.py
    git add tests/test_example.py

    run bash "$SCRIPT" tdd-baseline
    assert_failure
    assert_output --partial "FAIL"
    assert_output --partial "test_example.py"
}

@test "passes when only src files are modified" {
    # Add/modify a source file, leave tests alone
    mkdir -p src
    echo 'def hello(): return "world"' > src/main.py
    git add src/main.py

    run bash "$SCRIPT" tdd-baseline
    assert_success
}

@test "fails when a new test file is added during build" {
    # Add a new test file (not allowed during build)
    echo 'def test_new(): assert True' > tests/test_new.py
    git add tests/test_new.py

    run bash "$SCRIPT" tdd-baseline
    assert_failure
    assert_output --partial "test_new.py"
}
