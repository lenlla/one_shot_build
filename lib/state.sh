#!/usr/bin/env bash
# lib/state.sh — Utilities for execution state and progress logging
# Requires: yq (https://github.com/mikefarah/yq)

set -euo pipefail

# Determine project root (parent directory containing kyros-agent-workflow/)
# Can be overridden by setting PROJECT_ROOT before sourcing
PROJECT_ROOT="${PROJECT_ROOT:-$(pwd)}"

HARNESS_DIR="kyros-agent-workflow"

# Append a timestamped entry to the progress file for an epics directory
# Usage: log_progress "/path/to/epics/v1" "Completed step-01 implementation"
log_progress() {
    local epics_dir="$1"
    local message="$2"
    local progress_file="${epics_dir}/claude-progress.txt"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%d %H:%M:%S")

    echo "[${timestamp}] ${message}" >> "$progress_file"
}

# --- Execution state operations ---

# Resolve the path to .execution-state.yaml for a given epics directory
# Usage: execution_state_file "/path/to/epics/v1"
execution_state_file() {
    local epics_dir="$1"
    echo "${epics_dir}/.execution-state.yaml"
}

# Read a value from an execution state file
# Usage: read_execution_state "/path/to/epics/v1" "epics.data-loading.status"
read_execution_state() {
    local epics_dir="$1"
    local path="$2"
    local state_file
    state_file=$(execution_state_file "$epics_dir")

    if [[ ! -f "$state_file" ]]; then
        echo ""
        return 0
    fi

    local yq_path=".${path}"
    if command -v yq &>/dev/null; then
        local result
        result=$(yq eval "$yq_path" "$state_file" 2>/dev/null || echo "")
        if [[ "$result" == "null" ]]; then
            echo ""
        else
            echo "$result"
        fi
    else
        echo "Error: yq is required for execution state reads." >&2
        return 1
    fi
}

# Update a value in an execution state file
# Usage: update_execution_state "/path/to/epics/v1" "epics.data-loading.status" "completed"
update_execution_state() {
    local epics_dir="$1"
    local path="$2"
    local value="$3"
    local state_file
    state_file=$(execution_state_file "$epics_dir")

    if [[ ! -f "$state_file" ]]; then
        echo "Error: Execution state file not found at $state_file" >&2
        return 1
    fi

    local yq_path=".${path}"
    if command -v yq &>/dev/null; then
        yq eval -i "${yq_path} = \"${value}\"" "$state_file"
    else
        echo "Error: yq is required for execution state updates." >&2
        return 1
    fi
}

# Find all .execution-state.yaml files in the project
# Usage: find_execution_states
find_execution_states() {
    find "$PROJECT_ROOT" -name ".execution-state.yaml" -not -path "*/.git/*" 2>/dev/null || true
}

# Find active (non-completed) execution states
# Usage: find_active_executions
find_active_executions() {
    local states
    states=$(find_execution_states)

    if [[ -z "$states" ]]; then
        return 0
    fi

    while IFS= read -r state_file; do
        local epics_dir
        epics_dir=$(dirname "$state_file")
        # Check if any epic is not completed
        local pending
        pending=$(yq eval '.epics | to_entries | .[] | select(.value.status != "completed") | .key' "$state_file" 2>/dev/null || echo "")
        if [[ -n "$pending" ]]; then
            echo "$epics_dir"
        fi
    done <<< "$states"
}

# Get a human-readable summary of an execution state
# Usage: execution_summary "/path/to/epics/v1"
execution_summary() {
    local epics_dir="$1"
    local state_file
    state_file=$(execution_state_file "$epics_dir")

    if [[ ! -f "$state_file" ]]; then
        echo "No execution state found"
        return 0
    fi

    local total completed current_epic current_status current_step
    total=$(yq eval '.epics | length' "$state_file" 2>/dev/null || echo "0")
    completed=$(yq eval '.epics | to_entries | .[] | select(.value.status == "completed") | .key' "$state_file" 2>/dev/null | wc -l | tr -d ' ')
    current_epic=$(yq eval '.epics | to_entries | .[] | select(.value.status != "completed" and .value.status != "pending") | .key' "$state_file" 2>/dev/null | head -1)

    if [[ -n "$current_epic" ]]; then
        current_status=$(yq eval ".epics.\"${current_epic}\".status" "$state_file" 2>/dev/null || echo "")
        current_step=$(yq eval ".epics.\"${current_epic}\".current_step" "$state_file" 2>/dev/null || echo "")
        local steps_total
        steps_total=$(yq eval ".epics.\"${current_epic}\".steps_total" "$state_file" 2>/dev/null || echo "")
        if [[ -n "$current_step" && -n "$steps_total" && "$steps_total" != "null" ]]; then
            echo "${completed}/${total} epics done, currently on '${current_epic}' step ${current_step}/${steps_total}"
        else
            echo "${completed}/${total} epics done, currently on '${current_epic}' (${current_status})"
        fi
    else
        echo "${completed}/${total} epics done"
    fi
}
