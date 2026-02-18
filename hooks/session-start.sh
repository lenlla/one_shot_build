#!/usr/bin/env bash
# hooks/session-start.sh — Reads project-state.yaml and injects workflow context
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source state library
source "${PLUGIN_ROOT}/lib/state.sh"

# Escape string for JSON embedding
escape_for_json() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

# Build context message
context=""

if [[ -f "$STATE_FILE" ]]; then
    phase=$(get_current_phase)
    epic=$(get_current_epic)
    step=$(get_current_step)

    context="## One-Shot Build Harness Active\\n\\n"
    context+="**Current Phase:** ${phase:-not set}\\n"

    if [[ -n "$epic" ]]; then
        context+="**Current Epic:** ${epic}\\n"
    fi
    if [[ -n "$step" ]]; then
        context+="**Current Step:** ${step}\\n"
    fi

    context+="\\n**Next action:** "
    case "$phase" in
        gather_context)
            context+="Run \`/gather-context\` to begin data profiling and analyst Q&A."
            ;;
        define_epics)
            context+="Run \`/define-epics\` to collaboratively break down the project into epics."
            ;;
        plan)
            context+="Run \`/plan-epic\` to create a TDD plan for epic ${epic}."
            ;;
        build)
            context+="Run \`/build\` to start the agent team build/review loop for ${epic} / ${step}."
            ;;
        submit)
            context+="Run \`/submit\` to submit a PR for epic ${epic}."
            ;;
        *)
            context+="Run \`/status\` to check workflow state."
            ;;
    esac

    context+="\\n\\nRead \`${HARNESS_DIR}/project-state.yaml\` for full state. Read \`CLAUDE.md\` for project guide."
else
    context="## One-Shot Build Harness\\n\\n"
    context+="No project-state.yaml found in the current directory.\\n"
    context+="If this is a new project, run \`/init\` to scaffold it.\\n"
    context+="If this is an existing project, navigate to its root directory."
fi

# Warn if dangerous mode detected without VM isolation
if [[ -f "$PROJECT_ROOT/$HARNESS_DIR/.harnessrc" ]] && command -v yq &>/dev/null; then
    skip_perms=$(yq eval ".execution.skip_permissions" "$PROJECT_ROOT/$HARNESS_DIR/.harnessrc" 2>/dev/null)
    vm_id=$(yq eval ".execution.vm_id" "$PROJECT_ROOT/$HARNESS_DIR/.harnessrc" 2>/dev/null)
    if [[ "$skip_perms" == "true" && ( -z "$vm_id" || "$vm_id" == "null" ) ]]; then
        context+="\n\n⚠️ **WARNING:** skip_permissions is enabled but no vm_id is set.\n"
        context+="Ensure you are running on an isolated VM, not a developer machine.\n"
    fi
fi

escaped_context=$(escape_for_json "$context")

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "${escaped_context}"
  }
}
EOF

exit 0
