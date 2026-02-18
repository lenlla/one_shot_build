---
name: gather-context
description: Use when starting Phase 1 of a client project. Runs data profiling via the profiler agent and conducts analyst Q&A. Requires kyros-agent-workflow/project-state.yaml to show current_phase as gather_context.
---

# Gather Context

## Overview

Phase 1 of the one-shot-build workflow. Profile the client data and conduct a Q&A with the analyst to understand the project.

## Pre-Conditions

- `kyros-agent-workflow/project-state.yaml` exists with `workflow.current_phase: gather_context`
- Client data file is accessible (ask the user for the path if not known)

## Process

### Step 1: Locate the data
Use AskUserQuestion to ask: "Where is the client data file? (path to CSV/Excel/Parquet)"

### Step 2: Profile the data
Dispatch the **profiler** subagent with the Task tool:
- subagent_type: use the `profiler` agent definition
- Prompt: "Profile the data at [path]. Write results to kyros-agent-workflow/docs/context/data-profile.md."
- Wait for the profiler to complete

### Step 3: Review the profile
Read `kyros-agent-workflow/docs/context/data-profile.md` and present a summary to the analyst.
Highlight any data quality concerns (high nulls, low variance, type mismatches).

### Step 4: Analyst Q&A
Conduct an interactive Q&A session with the analyst. Ask ONE question at a time:
- What is the business objective for this project?
- What is the target variable?
- Are there known data quality issues?
- Are there columns that should be excluded?
- What is the expected output format?
- Any domain-specific constraints?

Save responses to `kyros-agent-workflow/docs/context/analyst-notes.md`.

### Step 5: Gate check
Use AskUserQuestion: "Does the data profile look complete? Ready to move to epic definition?"
- If yes: update `kyros-agent-workflow/project-state.yaml` → `workflow.current_phase: define_epics`
- If no: ask what needs further exploration

### Step 6: Commit and log progress
```bash
git add kyros-agent-workflow/docs/context/
git commit -m "docs: add data profile and analyst notes (Phase 1 complete)"
```

Log: "Phase 1 (gather context) complete. Data profiled, analyst Q&A conducted."

Tell the user: "Context gathered. Run `/define-epics` to break the project into epics."
