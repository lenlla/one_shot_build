#!/usr/bin/env bash
# hooks/definition-of-done.sh
# Runs the Definition of Done checklist before PR submission.
# Usage: definition-of-done.sh <epics-dir> [epic-name]
# Exit 0 = PASS, Exit 1 = FAIL with details

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source state library
source "${PLUGIN_ROOT}/lib/state.sh"

EPICS_DIR="${1:?Usage: definition-of-done.sh <epics-dir> [epic-name]}"
EPIC="${2:-}"

# If epic not provided, try to detect from execution state
if [[ -z "$EPIC" ]]; then
    local_state=$(execution_state_file "$EPICS_DIR")
    if [[ -f "$local_state" ]] && command -v yq &>/dev/null; then
        EPIC=$(yq eval '.epics | to_entries | .[] | select(.value.status == "submitting" or .value.status == "building") | .key' "$local_state" 2>/dev/null | head -1)
    fi
fi

if [[ -z "$EPIC" ]]; then
    echo "FAIL: Could not determine current epic. Provide epic name as second argument."
    exit 1
fi

failures=()

# --- Check 1: No TODO comments in src/ ---
if [[ -d "${HARNESS_DIR}/src" ]]; then
    todos=$(grep -rn "TODO\|FIXME\|HACK\|XXX" "${HARNESS_DIR}/src/" 2>/dev/null || true)
    if [[ -n "$todos" ]]; then
        failures+=("TODO/FIXME comments found in ${HARNESS_DIR}/src/:\n$todos")
    fi
fi

# --- Check 2: No debug print statements ---
if [[ -d "${HARNESS_DIR}/src" ]]; then
    debug_prints=$(grep -rn "print(" "${HARNESS_DIR}/src/" --include="*.py" 2>/dev/null | grep -v "# noqa" || true)
    if [[ -n "$debug_prints" ]]; then
        failures+=("Debug print() statements found in ${HARNESS_DIR}/src/:\n$debug_prints")
    fi
fi

# --- Check 3: claude-progress.txt exists and is non-empty ---
if [[ ! -s "$PROGRESS_FILE" ]]; then
    failures+=("claude-progress.txt is empty or missing")
fi

# --- Check 4: No uncommitted changes ---
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    failures+=("Uncommitted changes detected. Commit all work before submitting.")
fi

# --- Report ---
if [[ ${#failures[@]} -eq 0 ]]; then
    echo "PASS: All Definition of Done criteria met for epic ${EPIC}"
    exit 0
else
    echo "FAIL: Definition of Done check failed for epic ${EPIC}"
    echo ""
    for fail in "${failures[@]}"; do
        echo -e "  - $fail"
    done
    echo ""
    echo "Fix these issues before submitting."
    exit 1
fi
