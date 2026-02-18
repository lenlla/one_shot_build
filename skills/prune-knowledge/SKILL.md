---
name: prune-knowledge
description: Use periodically to review and clean up solution docs. Identifies stale, deprecated, superseded, and duplicate solutions across both project-level and team-level knowledge stores. Non-destructive — archives rather than deletes.
---

# Prune Knowledge

## Overview

Review all solution docs for staleness, contradictions, and low-value entries. Surface candidates to the human for review. Archive deprecated docs. This should be run periodically (e.g., at the start of a new project or quarterly).

## Process

### Step 1: Scan both tiers

Read `kyros-agent-workflow/.harnessrc` for `shared_knowledge_path`. Scan:
- `kyros-agent-workflow/docs/solutions/` (project-level)
- `<shared_knowledge_path>/docs/solutions/` (team-level, if configured)

For each solution doc, extract YAML frontmatter.

### Step 2: Auto-archive superseded docs

Find docs where `status: superseded` and `superseded_by` is filled.
Move them to `<category>/_archived/` subdirectory.

Report: "Archived N superseded docs."

### Step 3: Flag stale docs

Find active docs where `last_validated` is older than the staleness threshold
(default: 90 days, configurable via `kyros-agent-workflow/.harnessrc` under `pruning.staleness_threshold_days`).

Present to the user as a checklist:

```
## Potentially Stale Solutions (last validated > 90 days ago)

- [ ] **Null handling in target column** (last validated: 2026-01-15)
      kyros-agent-workflow/docs/solutions/model-library-issues/2026-01-15-null-target.md
      Action: [Still valid → refresh date] [Outdated → deprecate] [Skip]

- [ ] **PySpark broadcast join OOM** (last validated: 2025-11-20)
      kyros-agent-workflow/docs/solutions/pyspark-issues/2025-11-20-broadcast-oom.md
      Action: [Still valid → refresh date] [Outdated → deprecate] [Skip]
```

For each:
- "Still valid" → update `last_validated` to today
- "Outdated" → set `status: deprecated`, move to `_archived/`
- "Skip" → leave as-is for next review

### Step 4: Check version compatibility

Find active docs with `context.library_versions` or `context.tool_versions` constraints.
Compare against the current project's `kyros-agent-workflow/.harnessrc` profile.

Flag docs where version constraints are incompatible with the current project:

```
## Version-Incompatible Solutions

- **PySpark 3.2 shuffle fix** — requires pyspark: ">=3.2, <3.4", current project uses 3.5
  Action: [Deprecate] [Update version range] [Skip]
```

### Step 5: Detect duplicates

Find docs with the same `component` + `problem_type` + `root_cause` combination that are both `status: active`.

Present for merge or supersession:

```
## Duplicate Solutions (same component + problem_type + root_cause)

Group 1: model_execution / runtime_error / null_handling
  - 2026-01-15-null-target-workaround.md (workaround)
  - 2026-03-10-null-target-fix.md (code_fix)
  Action: [Merge into one] [Mark older as superseded] [Keep both] [Skip]
```

### Step 6: Summary report

```
## Pruning Summary

- Archived: N superseded docs
- Refreshed: N docs (last_validated updated)
- Deprecated: N stale/outdated docs
- Flagged for review: N version-incompatible docs
- Duplicate groups found: N
- Total active docs remaining: N (project) + N (team)
```

### Step 7: Commit changes

```bash
git add kyros-agent-workflow/docs/solutions/
git commit -m "chore: prune knowledge base — archive N, refresh N, deprecate N"
```

If team-level docs were modified:
```bash
cd <shared_knowledge_path>
git add docs/solutions/
git commit -m "chore: prune team knowledge — archive N, refresh N, deprecate N"
```

## Configuration

```yaml
# kyros-agent-workflow/.harnessrc
pruning:
  staleness_threshold_days: 90     # flag docs older than this
  auto_archive_superseded: true    # auto-archive without asking
```
