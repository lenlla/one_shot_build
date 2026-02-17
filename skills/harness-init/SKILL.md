---
name: harness-init
description: Use when starting a new client analytics project. Scaffolds project structure from templates with workflow state, standards docs, and CLAUDE.md.
---

# Initialize Project

## Overview

Scaffold a new client analytics project with the one-shot-build harness structure.

## Process

1. **Ask project name** — Use AskUserQuestion to get the project name
2. **Create directory structure** — Create all required directories
3. **Generate files from templates** — Replace `{{PROJECT_NAME}}` and `{{CREATED_DATE}}` placeholders
4. **Initialize git** — If not already a git repo, initialize one
5. **Create initial commit** — Commit the scaffolded structure
6. **Update state** — Set workflow phase to `gather_context`

## Directory Structure to Create

```
├── CLAUDE.md
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
│   └── plans/
├── config/
├── src/
│   └── utils/
├── tests/
├── scripts/
└── docs/
    └── solutions/                    # Per-project solution docs (compound learning)
        ├── data-quality-issues/
        ├── model-library-issues/
        ├── pyspark-issues/
        ├── performance-issues/
        ├── integration-issues/
        ├── best-practices/
        └── patterns/
            └── critical-patterns.md  # Always-read required knowledge
```

## Template Processing

For each template in the plugin's `templates/` directory:
1. Read the template file
2. Replace `{{PROJECT_NAME}}` with the user-provided project name
3. Replace `{{CREATED_DATE}}` with today's date in ISO format (YYYY-MM-DD)
4. Write to the corresponding path in the project root

Template mapping:
- `templates/CLAUDE.md.template` → `CLAUDE.md`
- `templates/project-state.yaml.template` → `project-state.yaml`
- `templates/definition-of-done.md.template` → `docs/standards/definition-of-done.md`
- `templates/review-criteria.md.template` → `docs/standards/review-criteria.md`
- `templates/coding-standards.md.template` → `docs/standards/coding-standards.md`
- `templates/.harnessrc.template` → `.harnessrc`

## After Scaffolding

Create an empty `claude-progress.txt` with a header line:

```
# Claude Progress Log — {{PROJECT_NAME}}
```

Create a seed `docs/solutions/patterns/critical-patterns.md`:

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
