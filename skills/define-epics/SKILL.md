---
name: define-epics
description: Use when Phase 1 is complete and it's time to break the project into epics. Collaboratively define epics with the analyst. Requires current_phase to be define_epics.
---

# Define Epics

## Overview

Phase 2 of the one-shot-build workflow. Collaboratively break the project into epics with the analyst.

## Pre-Conditions

- `kyros-agent-workflow/project-state.yaml` shows `workflow.current_phase: define_epics`
- `kyros-agent-workflow/docs/context/data-profile.md` and `kyros-agent-workflow/docs/context/analyst-notes.md` exist

## Process

### Step 1: Read context
Read `kyros-agent-workflow/docs/context/data-profile.md` and `kyros-agent-workflow/docs/context/analyst-notes.md` to understand the project.

### Step 2: Propose epic breakdown
Based on the data profile and analyst notes, propose a breakdown of the project into sequential epics. Present to the analyst:

```
## Proposed Epics

1. **Data Loading & Validation** — Load client data, validate schema, apply quality thresholds
2. **Data Translation** — Column renaming, type casting, variable grouping per config
3. **[Model Name] Execution** — Fit [model] with provided config and hyperparameters
4. **Report Generation** — Produce coefficient tables, predictions, summaries
...
```

### Step 3: Refine with analyst
Ask ONE question at a time to refine:
- "Does this epic breakdown match how you see the project?"
- "Should any epics be split or combined?"
- "What's the right order?"
- "Are there epics I'm missing?"

### Step 4: Write epic specs
For each agreed epic, create a YAML file in `kyros-agent-workflow/docs/epics/`:

```yaml
# kyros-agent-workflow/docs/epics/01-data-loading.yaml
name: "Data Loading & Validation"
description: "Load client data files, validate against schema, apply quality thresholds"
acceptance_criteria:
  - "All specified data files loaded successfully"
  - "Schema validation passes against project-config.yaml"
  - "Data quality thresholds enforced per data-quality-thresholds.yaml"
  - "Issue log written for any quality concerns"
dependencies: []
estimated_steps: 4
```

### Step 5: Update state
- Add all epics to `kyros-agent-workflow/project-state.yaml` under `epics:` with `status: pending`
- Set the first epic as `workflow.current_epic`
- Set `workflow.current_phase: plan`

### Step 6: Gate check
Use AskUserQuestion: "Epic breakdown is defined. Ready to start planning the first epic?"

### Step 7: Commit and log progress
```bash
git add kyros-agent-workflow/docs/epics/ kyros-agent-workflow/project-state.yaml
git commit -m "docs: define project epics (Phase 2 complete)"
```

Tell the user: "Epics defined. Run `/plan-epic` to create a TDD plan for the first epic."
