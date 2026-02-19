#!/usr/bin/env bash
# lib/state.sh — Utilities for execution state and progress logging
# Requires: yq (https://github.com/mikefarah/yq)

set -euo pipefail

# Determine project root (parent directory containing kyros-agent-workflow/)
# Can be overridden by setting PROJECT_ROOT before sourcing
PROJECT_ROOT="${PROJECT_ROOT:-$(pwd)}"

HARNESS_DIR="kyros-agent-workflow"

# Append a timestamped entry to the progress file for a build directory
# Usage: log_progress "/path/to/builds/v1" "Completed step-01 implementation"
log_progress() {
    local build_dir="$1"
    local message="$2"
    local progress_file="${build_dir}/claude-progress.txt"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%d %H:%M:%S")

    echo "[${timestamp}] ${message}" >> "$progress_file"
}

# --- Execution state operations ---

# Resolve the path to .execution-state.yaml for a given build directory
# Usage: execution_state_file "/path/to/builds/v1"
execution_state_file() {
    local build_dir="$1"
    echo "${build_dir}/.execution-state.yaml"
}

# Read a value from an execution state file
# Usage: read_execution_state "/path/to/builds/v1" "epics.data-loading.status"
read_execution_state() {
    local build_dir="$1"
    local path="$2"
    local state_file
    state_file=$(execution_state_file "$build_dir")

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
# Usage: update_execution_state "/path/to/builds/v1" "epics.data-loading.status" "completed"
update_execution_state() {
    local build_dir="$1"
    local path="$2"
    local value="$3"
    local state_file
    state_file=$(execution_state_file "$build_dir")

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
        local build_dir
        build_dir=$(dirname "$state_file")
        # Check if any epic is not completed
        local pending
        pending=$(yq eval '.epics | to_entries | .[] | select(.value.status != "completed") | .key' "$state_file" 2>/dev/null || echo "")
        if [[ -n "$pending" ]]; then
            echo "$build_dir"
        fi
    done <<< "$states"
}

# Get a human-readable summary of an execution state
# Usage: execution_summary "/path/to/builds/v1"
execution_summary() {
    local build_dir="$1"
    local state_file
    state_file=$(execution_state_file "$build_dir")

    if [[ ! -f "$state_file" ]]; then
        echo "No execution state found"
        return 0
    fi

    local total completed current_epic current_status
    total=$(yq eval '.epics | length' "$state_file" 2>/dev/null || echo "0")
    completed=$(yq eval '.epics | to_entries | .[] | select(.value.status == "completed") | .key' "$state_file" 2>/dev/null | wc -l | tr -d ' ')
    current_epic=$(yq eval '.epics | to_entries | .[] | select(.value.status != "completed" and .value.status != "pending") | .key' "$state_file" 2>/dev/null | head -1)

    if [[ -n "$current_epic" ]]; then
        current_status=$(yq eval ".epics.\"${current_epic}\".status" "$state_file" 2>/dev/null || echo "")

        # Check for step-level tracking
        local steps_total steps_completed
        steps_total=$(yq eval ".epics.\"${current_epic}\".steps | length" "$state_file" 2>/dev/null || echo "0")
        steps_completed=$(yq eval ".epics.\"${current_epic}\".steps | to_entries | .[] | select(.value.status == \"completed\") | .key" "$state_file" 2>/dev/null | wc -l | tr -d ' ')

        if [[ "$steps_total" -gt 0 ]]; then
            echo "${completed}/${total} epics done, currently on '${current_epic}' step ${steps_completed}/${steps_total}"
        else
            echo "${completed}/${total} epics done, currently on '${current_epic}' (${current_status})"
        fi
    else
        echo "${completed}/${total} epics done"
    fi
}

# --- Step-level state operations ---

# Read the status of a specific step within an epic
# Usage: read_step_status "/path/to/builds/v1" "data-loading" "step-01"
read_step_status() {
    local build_dir="$1"
    local epic_name="$2"
    local step_name="$3"
    read_execution_state "$build_dir" "epics.\"${epic_name}\".steps.\"${step_name}\".status"
}

# Update the status of a specific step within an epic
# Usage: update_step_status "/path/to/builds/v1" "data-loading" "step-01" "completed"
update_step_status() {
    local build_dir="$1"
    local epic_name="$2"
    local step_name="$3"
    local status="$4"
    update_execution_state "$build_dir" "epics.\"${epic_name}\".steps.\"${step_name}\".status" "$status"
    # Also update current_step pointer
    if [[ "$status" == "in_progress" ]]; then
        update_execution_state "$build_dir" "epics.\"${epic_name}\".current_step" "$step_name"
    fi
}

# Parse implementation plan and initialize step entries in execution state
# Usage: init_steps_from_plan "/path/to/builds/v1" "data-loading" "/path/to/plan.md"
init_steps_from_plan() {
    local build_dir="$1"
    local epic_name="$2"
    local plan_path="$3"
    local state_file
    state_file=$(execution_state_file "$build_dir")

    if [[ ! -f "$plan_path" ]]; then
        echo "Error: Plan file not found at $plan_path" >&2
        return 1
    fi

    # Extract task headings: "### Task N: [Name]" -> "task-n-name-slug"
    local step_names
    step_names=$(grep -E '^### Task [0-9]+:' "$plan_path" | sed -E 's/^### Task ([0-9]+): (.*)$/\1 \2/' | while read -r num name; do
        # Convert to slug: lowercase, spaces to dashes, strip non-alphanumeric
        local slug
        slug=$(echo "$name" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9 ]//g' | tr ' ' '-' | sed 's/--*/-/g' | sed 's/-$//')
        echo "task-${num}-${slug}"
    done)

    if [[ -z "$step_names" ]]; then
        echo "Error: No task headings found in plan at $plan_path" >&2
        return 1
    fi

    # Create step entries in the execution state
    while IFS= read -r step_name; do
        yq eval -i ".epics.\"${epic_name}\".steps.\"${step_name}\".status = \"pending\"" "$state_file"
    done <<< "$step_names"
}

# Get the next pending step for an epic
# Usage: get_next_pending_step "/path/to/builds/v1" "data-loading"
get_next_pending_step() {
    local build_dir="$1"
    local epic_name="$2"
    local state_file
    state_file=$(execution_state_file "$build_dir")

    if [[ ! -f "$state_file" ]]; then
        echo ""
        return 0
    fi

    local result
    result=$(yq eval ".epics.\"${epic_name}\".steps | to_entries | .[] | select(.value.status != \"completed\") | .key" "$state_file" 2>/dev/null || true)
    echo "$result" | head -1
}

# Increment the review round counter for a step
# Usage: increment_review_rounds "/path/to/builds/v1" "data-loading" "step-01"
increment_review_rounds() {
    local build_dir="$1"
    local epic_name="$2"
    local step_name="$3"
    local state_file
    state_file=$(execution_state_file "$build_dir")

    local current
    current=$(yq eval ".epics.\"${epic_name}\".steps.\"${step_name}\".review_rounds // 0" "$state_file" 2>/dev/null)
    local next=$((current + 1))
    yq eval -i ".epics.\"${epic_name}\".steps.\"${step_name}\".review_rounds = ${next}" "$state_file"
}
