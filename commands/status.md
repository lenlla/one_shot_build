---
description: "Check workflow state: active executions, progress, and available commands."
disable-model-invocation: true
---

Check the current workflow state by doing the following:

1. **Scan for execution states:** Look for `.execution-state.yaml` files in the project (search recursively for files named `.execution-state.yaml`).

2. **For each execution state found:**
   - Read the file
   - Report: directory path, mode (interactive/autonomous), epic progress (N of M complete), current epic and step if in progress

3. **Check for data profiles:** Look for `kyros-agent-workflow/docs/context/data-profile-*.md` files. If found, list them.

4. **Check for epic directories:** Look for directories containing `.yaml` epic spec files. List any found.

5. **Present a summary** showing:
   - Active executions (if any)
   - Available data profiles (if any)
   - Defined epic directories (if any)
   - Suggested next command based on what exists

6. **Available commands reminder:**
   - `/init` — Scaffold a new project
   - `/profile-data` — Profile data tables
   - `/define-epics` — Brainstorm and define epics
   - `/execute-plan <dir>` — Execute epics interactively
   - `/execute-plan-autonomously <dir>` — Execute epics autonomously
   - `/board` — Open Kanban dashboard
   - `/prune-knowledge` — Review and cleanup solution docs
