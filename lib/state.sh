#!/usr/bin/env bash
# lib/state.sh — Utilities for reading/updating project-state.yaml
# Requires: yq (https://github.com/mikefarah/yq) or falls back to grep/sed

set -euo pipefail

# Determine project root (parent directory containing kyros-agent-workflow/)
# Can be overridden by setting PROJECT_ROOT before sourcing
PROJECT_ROOT="${PROJECT_ROOT:-$(pwd)}"

HARNESS_DIR="kyros-agent-workflow"
STATE_FILE="${PROJECT_ROOT}/${HARNESS_DIR}/project-state.yaml"
PROGRESS_FILE="${PROJECT_ROOT}/${HARNESS_DIR}/claude-progress.txt"

# --- Core YAML operations ---

# Read a dot-separated path from the state file
# Usage: read_state "workflow.current_phase"
read_state() {
    local path="$1"

    if [[ ! -f "$STATE_FILE" ]]; then
        echo ""
        return 0
    fi

    # Convert dot path to yq path: workflow.current_phase -> .workflow.current_phase
    local yq_path=".${path}"

    if command -v yq &>/dev/null; then
        local result
        result=$(yq eval "$yq_path" "$STATE_FILE" 2>/dev/null || echo "")
        # yq returns "null" for missing keys
        if [[ "$result" == "null" ]]; then
            echo ""
        else
            echo "$result"
        fi
    else
        # Fallback: simple grep-based extraction for flat keys
        # This only works for simple key: value pairs, not nested structures
        local key="${path##*.}"
        grep -E "^\s*${key}:" "$STATE_FILE" 2>/dev/null | head -1 | sed 's/.*:\s*//' | tr -d '"' | tr -d "'" || echo ""
    fi
}

# Update a dot-separated path in the state file
# Usage: update_state "workflow.current_phase" "build"
update_state() {
    local path="$1"
    local value="$2"

    if [[ ! -f "$STATE_FILE" ]]; then
        echo "Error: State file not found at $STATE_FILE" >&2
        return 1
    fi

    local yq_path=".${path}"

    if command -v yq &>/dev/null; then
        yq eval -i "${yq_path} = \"${value}\"" "$STATE_FILE"
    else
        echo "Error: yq is required for state updates. Install from https://github.com/mikefarah/yq" >&2
        return 1
    fi
}

# --- Convenience functions ---

get_current_phase() {
    read_state "workflow.current_phase"
}

get_current_epic() {
    read_state "workflow.current_epic"
}

get_current_step() {
    read_state "workflow.current_step"
}

# Append a timestamped entry to the progress file
# Usage: log_progress "Completed step-01 implementation"
log_progress() {
    local message="$1"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%d %H:%M:%S")

    echo "[${timestamp}] ${message}" >> "$PROGRESS_FILE"
}
