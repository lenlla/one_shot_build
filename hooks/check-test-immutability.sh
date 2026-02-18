#!/usr/bin/env bash
# hooks/check-test-immutability.sh
# Checks that no test files have been modified since the TDD baseline commit.
# Usage: check-test-immutability.sh <baseline-ref>
# Exit 0 = PASS (no test modifications)
# Exit 1 = FAIL (test files were modified)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${PLUGIN_ROOT}/lib/state.sh"

BASELINE_REF="${1:-tdd-baseline}"

# Get list of test files changed since baseline
changed_tests=$(git diff --name-only "$BASELINE_REF" -- "${HARNESS_DIR}/tests/" "*/${HARNESS_DIR}/tests/" '**/test_*' '**/*_test.*' 2>/dev/null || echo "")

# Also check staged changes
staged_tests=$(git diff --cached --name-only "$BASELINE_REF" -- "${HARNESS_DIR}/tests/" "*/${HARNESS_DIR}/tests/" '**/test_*' '**/*_test.*' 2>/dev/null || echo "")

# Combine and deduplicate
all_changed=$(echo -e "${changed_tests}\n${staged_tests}" | sort -u | grep -v '^$' || true)

if [[ -z "$all_changed" ]]; then
    echo "PASS: No test files modified since TDD baseline ($BASELINE_REF)"
    exit 0
else
    echo "FAIL: Test files modified during build phase (baseline: $BASELINE_REF)"
    echo ""
    echo "Modified test files:"
    echo "$all_changed" | while read -r file; do
        echo "  - $file"
    done
    echo ""
    echo "Tests are immutable during the build phase. If tests need to change,"
    echo "go back to the planning phase (/plan-epic) to update them."
    exit 1
fi
