---
name: harness-init
description: Use when starting a new client analytics project. Scaffolds project structure from templates with workflow state, standards docs, and CLAUDE.md.
---

# Initialize Project

## Overview

Scaffold a new client analytics project with the one-shot-build harness structure.

## Process

1. **Check for existing project** — If `kyros-agent-workflow/project-state.yaml` already exists in the current directory, STOP and tell the user: "This directory already has a one-shot-build project. Run `/status` to see its state." Do NOT overwrite existing files.
2. **Ask project name** — Use AskUserQuestion to get the project name
3. **Create directory structure** — Create all required directories
4. **Generate files from templates** — Replace `{{PROJECT_NAME}}` and `{{CREATED_DATE}}` placeholders
5. **Initialize git** — If not already a git repo, initialize one
6. **Create initial commit** — Commit the scaffolded structure
7. **Update state** — Set workflow phase to `gather_context`

## Directory Structure to Create

```
├── CLAUDE.md
└── kyros-agent-workflow/
    ├── project-state.yaml
    ├── claude-progress.txt
    ├── .harnessrc
    ├── docs/
    │   ├── context/
    │   ├── epics/
    │   ├── standards/
    │   │   ├── coding-standards.md
    │   │   ├── definition-of-done.md
    │   │   └── review-criteria.md
    │   ├── plans/
    │   └── solutions/
    │       ├── data-quality-issues/
    │       │   └── _archived/
    │       ├── model-library-issues/
    │       │   └── _archived/
    │       ├── pyspark-issues/
    │       │   └── _archived/
    │       ├── performance-issues/
    │       │   └── _archived/
    │       ├── integration-issues/
    │       │   └── _archived/
    │       ├── best-practices/
    │       │   └── _archived/
    │       └── patterns/
    │           └── critical-patterns.md
    ├── config/
    ├── src/
    │   └── utils/
    ├── tests/
    └── scripts/
```

## Template Processing

For each template in the plugin's `templates/` directory:
1. Read the template file
2. Replace `{{PROJECT_NAME}}` with the user-provided project name
3. Replace `{{CREATED_DATE}}` with today's date in ISO format (YYYY-MM-DD)
4. Write to the corresponding path (CLAUDE.md at project root, everything else under kyros-agent-workflow/)

Template mapping:
- `templates/CLAUDE.md.template` → `CLAUDE.md`
- `templates/project-state.yaml.template` → `kyros-agent-workflow/project-state.yaml`
- `templates/definition-of-done.md.template` → `kyros-agent-workflow/docs/standards/definition-of-done.md`
- `templates/review-criteria.md.template` → `kyros-agent-workflow/docs/standards/review-criteria.md`
- `templates/coding-standards.md.template` → `kyros-agent-workflow/docs/standards/coding-standards.md`
- `templates/.harnessrc.template` → `kyros-agent-workflow/.harnessrc`

## After Scaffolding

Create an empty `kyros-agent-workflow/claude-progress.txt` with a header line:

```
# Claude Progress Log — {{PROJECT_NAME}}
```

Create a seed `kyros-agent-workflow/docs/solutions/patterns/critical-patterns.md`:

```markdown
# Critical Patterns

> This file is ALWAYS read by the learnings-researcher agent. Add patterns here
> that every developer/agent must know about for this project.

<!-- Add critical patterns as they are discovered -->
```

Log the initialization:

```
[timestamp] Project initialized with one-shot-build harness. Phase: gather_context.
```

## Completion

Tell the user: "Project scaffolded. Run `/gather-context` to begin data profiling and analyst Q&A."
