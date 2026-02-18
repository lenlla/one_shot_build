#!/usr/bin/env bash
# hooks/self-check.sh
# Runs all pre-completion checks. Intended to be called by the developer
# agent before marking a task complete, as a self-verification step.
# Usage: self-check.sh <step-name> <epic-name> [tdd-baseline-ref]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${PLUGIN_ROOT}/lib/state.sh"

STEP="${1:?Usage: self-check.sh <step-name> <epic-name> [tdd-baseline-ref]}"
EPIC="${2:?Usage: self-check.sh <step-name> <epic-name> [tdd-baseline-ref]}"
BASELINE="${3:-tdd-baseline}"

echo "=== Self-Verification Check ==="
echo "Step: $STEP | Epic: $EPIC"
echo ""

passed=0
failed=0

# Check 1: Tests pass
echo "--- Running tests ---"
if pytest "${HARNESS_DIR}/tests/" -v --tb=short 2>&1; then
    echo "  PASS: Tests"
    passed=$((passed + 1))
else
    echo "  FAIL: Tests"
    failed=$((failed + 1))
fi
echo ""

# Check 2: Test immutability
echo "--- Checking test immutability ---"
if bash "${SCRIPT_DIR}/check-test-immutability.sh" "$BASELINE" 2>&1; then
    passed=$((passed + 1))
else
    failed=$((failed + 1))
fi
echo ""

# Check 3: Validate any new solution docs
echo "--- Validating solution docs ---"
SCHEMA="${SCRIPT_DIR}/../lib/solution-schema.yaml"
new_docs=$(git diff --name-only --diff-filter=A HEAD -- "${HARNESS_DIR}/docs/solutions/*.md" "${HARNESS_DIR}/docs/solutions/**/*.md" 2>/dev/null || true)
if [[ -n "$new_docs" ]]; then
    doc_pass=true
    while IFS= read -r doc; do
        if ! bash "${SCRIPT_DIR}/validate-solution-doc.sh" "$doc" "$SCHEMA" 2>&1; then
            doc_pass=false
        fi
    done <<< "$new_docs"
    if [[ "$doc_pass" == "true" ]]; then
        echo "  PASS: All solution docs valid"
        passed=$((passed + 1))
    else
        echo "  FAIL: Solution doc validation failed"
        failed=$((failed + 1))
    fi
else
    echo "  SKIP: No new solution docs"
    passed=$((passed + 1))
fi
echo ""

# Check 4: No uncommitted changes
echo "--- Checking git status ---"
if [[ -z "$(git status --porcelain 2>/dev/null)" ]]; then
    echo "  PASS: All changes committed"
    passed=$((passed + 1))
else
    echo "  FAIL: Uncommitted changes detected"
    failed=$((failed + 1))
fi
echo ""

# Summary
echo "=== Self-Check Complete ==="
echo "$passed passed, $failed failed"

if [[ $failed -gt 0 ]]; then
    echo "Fix the above issues before marking the step complete."
    exit 1
else
    echo "All checks pass. Safe to mark step as complete."
    exit 0
fi
