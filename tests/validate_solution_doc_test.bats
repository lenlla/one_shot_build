#!/usr/bin/env bats
# tests/validate_solution_doc_test.bats

setup() {
    load "${BATS_TEST_DIRNAME}/../node_modules/bats-support/load"
    load "${BATS_TEST_DIRNAME}/../node_modules/bats-assert/load"

    TEST_DIR="$(mktemp -d)"
    SCRIPT="${BATS_TEST_DIRNAME}/../hooks/validate-solution-doc.sh"
    SCHEMA="${BATS_TEST_DIRNAME}/../lib/solution-schema.yaml"
}

teardown() {
    rm -rf "$TEST_DIR"
}

@test "passes for a valid solution doc" {
    cat > "$TEST_DIR/valid-doc.md" <<'EOF'
---
title: "Null handling in target column"
date: 2026-03-10
problem_type: runtime_error
component: model_execution
severity: critical
root_cause: null_handling
resolution_type: code_fix
applies_to:
  scope: universal
  project_types: []
  data_characteristics: []
  tools: [custom_model_library]
tags: [null-handling]
---

## Problem
Model library crashes on null target.

## Solution
Add null check before calling library.
EOF

    run bash "$SCRIPT" "$TEST_DIR/valid-doc.md" "$SCHEMA"
    assert_success
    assert_output --partial "PASS"
}

@test "fails when problem_type has invalid enum value" {
    cat > "$TEST_DIR/invalid-doc.md" <<'EOF'
---
title: "Test doc"
date: 2026-03-10
problem_type: banana
component: model_execution
severity: critical
root_cause: null_handling
resolution_type: code_fix
applies_to:
  scope: universal
  project_types: []
  data_characteristics: []
  tools: []
tags: []
---

## Problem
Test.
EOF

    run bash "$SCRIPT" "$TEST_DIR/invalid-doc.md" "$SCHEMA"
    assert_failure
    assert_output --partial "problem_type"
}

@test "fails when required frontmatter fields are missing" {
    cat > "$TEST_DIR/missing-fields.md" <<'EOF'
---
title: "Test doc"
date: 2026-03-10
---

## Problem
Test.
EOF

    run bash "$SCRIPT" "$TEST_DIR/missing-fields.md" "$SCHEMA"
    assert_failure
    assert_output --partial "missing"
}

@test "fails when status has invalid enum value" {
    cat > "$TEST_DIR/bad-status.md" <<'EOF'
---
title: "Test doc"
date: 2026-03-10
problem_type: runtime_error
component: model_execution
severity: critical
root_cause: null_handling
resolution_type: code_fix
status: banana
applies_to:
  scope: universal
  project_types: []
  data_characteristics: []
  tools: []
tags: []
---

## Problem
Test.
EOF

    run bash "$SCRIPT" "$TEST_DIR/bad-status.md" "$SCHEMA"
    assert_failure
    assert_output --partial "status"
}

@test "detects contradiction with existing doc (same component+problem_type+root_cause)" {
    mkdir -p "$TEST_DIR/docs/solutions/model-library-issues"
    cat > "$TEST_DIR/docs/solutions/model-library-issues/old-doc.md" <<'EOF'
---
title: "Old null handling fix"
date: 2026-02-01
problem_type: runtime_error
component: model_execution
root_cause: null_handling
severity: high
resolution_type: workaround
status: active
applies_to:
  scope: universal
  project_types: []
  data_characteristics: []
  tools: []
tags: []
---

## Problem
Old workaround.
EOF

    cat > "$TEST_DIR/new-doc.md" <<'EOF'
---
title: "Better null handling fix"
date: 2026-03-10
problem_type: runtime_error
component: model_execution
root_cause: null_handling
severity: critical
resolution_type: code_fix
status: active
applies_to:
  scope: universal
  project_types: []
  data_characteristics: []
  tools: []
tags: []
---

## Problem
Better fix.
EOF

    run bash "$SCRIPT" "$TEST_DIR/new-doc.md" "$SCHEMA" "$TEST_DIR/docs/solutions"
    assert_success
    # Should pass validation but warn about overlap
    assert_output --partial "OVERLAP"
}
