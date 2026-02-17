#!/usr/bin/env bash
# hooks/definition-of-done.sh
# Runs the Definition of Done checklist before PR submission.
# Exit 0 = PASS, Exit 1 = FAIL with details

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source state library
source "${PLUGIN_ROOT}/lib/state.sh"

failures=()

# --- Check 1: All steps have tests_pass: true and review_approved: true ---
epic=$(get_current_epic)

if command -v yq &>/dev/null && [[ -f "$STATE_FILE" ]]; then
    # Check for any steps without tests_pass: true
    unapproved=$(yq eval ".epics.${epic}.steps | to_entries | .[] | select(.value.tests_pass != true or .value.review_approved != true) | .key" "$STATE_FILE" 2>/dev/null || echo "")
    if [[ -n "$unapproved" ]]; then
        failures+=("Steps missing tests_pass or review_approved: $unapproved")
    fi
fi

# --- Check 2: No TODO comments in src/ ---
if [[ -d "src" ]]; then
    todos=$(grep -rn "TODO\|FIXME\|HACK\|XXX" src/ 2>/dev/null || true)
    if [[ -n "$todos" ]]; then
        failures+=("TODO/FIXME comments found in src/:\n$todos")
    fi
fi

# --- Check 3: No debug print statements ---
if [[ -d "src" ]]; then
    debug_prints=$(grep -rn "print(" src/ --include="*.py" 2>/dev/null | grep -v "# noqa" || true)
    if [[ -n "$debug_prints" ]]; then
        failures+=("Debug print() statements found in src/:\n$debug_prints")
    fi
fi

# --- Check 4: claude-progress.txt exists and is non-empty ---
if [[ ! -s "$PROGRESS_FILE" ]]; then
    failures+=("claude-progress.txt is empty or missing")
fi

# --- Check 5: No uncommitted changes ---
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    failures+=("Uncommitted changes detected. Commit all work before submitting.")
fi

# --- Report ---
if [[ ${#failures[@]} -eq 0 ]]; then
    echo "PASS: All Definition of Done criteria met for epic ${epic}"
    exit 0
else
    echo "FAIL: Definition of Done check failed for epic ${epic}"
    echo ""
    for fail in "${failures[@]}"; do
        echo -e "  - $fail"
    done
    echo ""
    echo "Fix these issues before running /submit."
    exit 1
fi
