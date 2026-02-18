#!/usr/bin/env bash
# hooks/session-start.sh — Scans for active execution states and injects workflow context
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

# Check for active execution states
active_dirs=$(find_active_executions)

if [[ -n "$active_dirs" ]]; then
    # Count active executions
    active_count=$(echo "$active_dirs" | wc -l | tr -d ' ')

    if [[ "$active_count" -eq 1 ]]; then
        dir=$(echo "$active_dirs" | head -1)
        summary=$(execution_summary "$dir")
        context="## One-Shot Build Harness Active\\n\\n"
        context+="**Active execution:** \`${dir}\` — ${summary}\\n\\n"
        context+="Run \`/execute-plan ${dir}\` to resume."
    else
        context="## One-Shot Build Harness Active\\n\\n"
        context+="**Active executions:**\\n\\n"
        while IFS= read -r dir; do
            summary=$(execution_summary "$dir")
            context+="  - \`${dir}\` — ${summary}\\n"
        done <<< "$active_dirs"
        context+="\\nRun \`/execute-plan <dir>\` to resume one."
    fi

    context+="\\n\\nOther commands: \`/profile-data\`, \`/define-epics\`, \`/status\`, \`/board\`"
else
    context="## One-Shot Build Harness\\n\\n"
    context+="No active executions found.\\n\\n"
    context+="**Available commands:**\\n"
    context+="- \`/init\` — Scaffold a new project\\n"
    context+="- \`/profile-data\` — Profile data tables\\n"
    context+="- \`/define-epics\` — Brainstorm and define project epics\\n"
    context+="- \`/execute-plan <dir>\` — Execute epics interactively\\n"
    context+="- \`/execute-plan-autonomously <dir>\` — Execute epics autonomously\\n"
    context+="- \`/status\` — Check workflow state\\n"
    context+="- \`/board\` — Open Kanban dashboard"
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
