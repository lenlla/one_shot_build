# Design: One-Shot Build Harness Architecture

**Date:** 2026-02-16
**Status:** Approved
**Authors:** Human (analyst/architect) + Claude Code (design partner)

## Overview

A Claude Code plugin that governs the agent's development workflow when executing client predictive modeling projects. The plugin provides structured skills, hooks, agent team coordination, and mechanical enforcement to ensure Claude Code follows a disciplined process from data profiling through to final deliverables.

This is NOT a data pipeline framework. The team already has a DAG-based execution pipeline. This harness operates one level above that: it manages the agent's workflow as a developer — like a Kanban board with deterministic quality gates.

**Core principle:** Humans steer. Agents execute.

## Context

- **Runtime:** PySpark everywhere (local Docker container + Databricks)
- **Modeling:** Calls into a custom in-house Python library (interface TBD)
- **Pipeline:** A chain of many analytical steps, not a single model
- **Existing infrastructure:** DAG-based execution pipeline already built
- **Transportability:** The harness must work across any client project, not just one repo
- **Execution environment:** Isolated VM with `dangerouslySkipPermissions` mode for fully autonomous operation
- **Databricks integration:** MCP server for remote code execution on Databricks clusters

## Architecture: Plugin + Project Split

The harness is a Claude Code plugin (installed once per developer) that scaffolds and governs per-project repos.

### Part 1: The Plugin (reusable)

```
one-shot-build/                        # Claude Code plugin
├── .claude-plugin/
│   └── plugin.json                    # Plugin metadata
├── skills/
│   ├── harness-init/SKILL.md          # Scaffold a new client project
│   ├── gather-context/SKILL.md        # Phase 1: data profiling + analyst Q&A
│   ├── define-epics/SKILL.md          # Collaborative epic breakdown
│   ├── plan-epic/SKILL.md             # Phase 2: TDD planning for an epic
│   ├── build-step/SKILL.md            # Phase 3: start agent team build/review loop
│   ├── review-step/SKILL.md           # Phase 3: invoke review agent
│   ├── submit-epic/SKILL.md           # Phase 4: PR + advance state
│   ├── quality-scan/SKILL.md          # Background quality/deviation scan
│   ├── harness-status/SKILL.md        # Check workflow state, show next action
│   ├── prune-knowledge/SKILL.md      # Periodic knowledge base cleanup and archival
│   └── run-on-databricks/SKILL.md    # When/how to use Databricks vs local PySpark
├── hooks/
│   ├── hooks.json                     # Hook config (SessionStart, TaskCompleted, TeammateIdle)
│   ├── session-start.sh               # Read state file, sync tasks, show current phase
│   ├── check-test-immutability.sh     # Detect unauthorized test modifications during build
│   ├── definition-of-done.sh          # Pre-PR quality checklist
│   ├── validate-solution-doc.sh       # Validate solution doc YAML frontmatter against schema
│   ├── quality-scan.sh               # Background quality/deviation scan
│   └── self-check.sh                 # Developer self-verification wrapper (all checks)
├── commands/
│   ├── init.md                        # /init shorthand
│   ├── status.md                      # /status shorthand
│   ├── next.md                        # /next — advance to next step
│   ├── prune-knowledge.md             # /prune-knowledge — clean up stale solution docs
│   └── board.md                       # /board — launch Kanban dashboard
├── agents/
│   ├── reviewer.md                    # Review agent: separate prompt, critical evaluation
│   ├── profiler.md                    # Data profiling agent for context gathering
│   └── learnings-researcher.md        # Pull-based knowledge retrieval from solution docs
├── templates/                         # Scaffolding templates for new projects
│   ├── CLAUDE.md.template
│   ├── project-state.yaml.template
│   ├── definition-of-done.md.template
│   ├── review-criteria.md.template
│   ├── coding-standards.md.template
│   └── .harnessrc.template
├── mcp/
│   └── databricks-executor/
│       ├── server.py                  # MCP server for Databricks operations
│       ├── requirements.txt
│       └── README.md
├── dashboard/
│   ├── index.html                    # Kanban board single-page app
│   ├── style.css
│   ├── app.js                        # YAML parsing + board rendering
│   └── serve.sh                      # Local server launcher
└── lib/
    ├── state.sh                       # Utilities for reading/updating project-state.yaml
    └── solution-schema.yaml           # Valid enum values for solution doc frontmatter
```

### Part 2: Client Project (generated per project via `/init`)

```
client-project-xyz/
├── CLAUDE.md                          # ~100 lines, table of contents (not a manual)
├── project-state.yaml                 # Workflow state machine
├── claude-progress.txt                # Running activity log
├── .harnessrc                         # Per-project config overrides
├── docs/
│   ├── context/                       # Phase 1 outputs
│   │   ├── data-profile.md
│   │   └── analyst-notes.md
│   ├── epics/                         # Epic definitions (YAML, one per epic)
│   │   └── 01-<epic>.yaml
│   ├── standards/                     # Quality standards (from templates)
│   │   ├── coding-standards.md
│   │   ├── definition-of-done.md
│   │   └── review-criteria.md
│   ├── plans/                         # Implementation plans per epic
│   └── solutions/                     # Per-project solution docs (compound learning)
│       ├── data-quality-issues/
│       ├── model-library-issues/
│       ├── pyspark-issues/
│       ├── performance-issues/
│       ├── integration-issues/
│       ├── best-practices/
│       └── patterns/
│           └── critical-patterns.md   # Always-read required knowledge
├── config/
│   ├── project-config.yaml            # Human decisions (mappings, predictors, hyperparameters)
│   └── data-quality-thresholds.yaml   # Defaults + overrides
├── src/
├── tests/
└── scripts/                           # Project-specific enforcement scripts
```

## Workflow Phases

### Phase 1: Gather Context (`/gather-context`)

- Spin up Profiler agent to run PySpark exploration queries (distributions, nulls, cardinality, types, outliers)
- Generate `docs/context/data-profile.md`
- Interactive Q&A with the analyst to understand business objectives, constraints, known issues
- Save `docs/context/analyst-notes.md`
- **Gate:** Analyst approves the data profile

### Phase 2: Define Epics (`/define-epics`)

- Claude proposes epic breakdown based on context + PRD
- Interactive refinement with the analyst (one question at a time)
- Generate YAML files in `docs/epics/` (one per epic)
- **Gate:** Analyst approves the epic breakdown

### Phase 3: Plan Epic (`/plan-epic`)

- Read current epic spec from `docs/epics/`
- Break it into steps with acceptance criteria
- Write tests FIRST (TDD) — tests become immutable during build phase
- Generate implementation plan in `docs/plans/`
- **Gate:** Tests written, plan approved

### Phase 4: Build + Review Loop (`/build`)

- Create agent team: lead (delegate mode) + developer teammate + reviewer teammate
- Populate shared task list from current epic's steps
- Developer claims tasks, implements, commits with descriptive messages
- Reviewer reviews with direct feedback to developer (no relay through lead)
- Loop until reviewer approves each step
- Circuit breaker monitors for stuck loops
- **Gate:** All steps pass tests + review approved

### Phase 5: Submit + Advance (`/submit`)

- Run definition-of-done checklist
- Create PR with epic summary
- Update `project-state.yaml` (mark epic complete, advance to next)
- **Gate:** PR merged by human
- Return to Phase 3 for next epic

```
/init -> /gather-context -> /define-epics -> /plan-epic -> /build -> /submit
                                                  ^                    |
                                                  └────────────────────┘
                                                  (loop for each epic)
```

## State Management

### Dual-System Approach

| Aspect | `project-state.yaml` | Claude Code Tasks |
|---|---|---|
| **Purpose** | Canonical source of truth | Active working interface |
| **Storage** | In project repo (git-versioned) | `~/.claude/tasks` (session-scoped) |
| **Audience** | Humans + harness | Claude Code agent |
| **Persistence** | Permanent, auditable | Temporary, per-session |
| **Structure** | Full hierarchy (phase -> epic -> step) | Flat list with dependencies |

The `SessionStart` hook syncs Claude Code tasks from `project-state.yaml`. When a task completes, both systems are updated. The state file is committed to git for auditability.

### State File Structure

```yaml
project:
  name: "Client XYZ Churn Model"
  created: "2026-02-16"

workflow:
  current_phase: "build"
  current_epic: "02-data-translation"
  current_step: "step-03-type-casting"

phases:
  gather_context:
    status: completed
    completed_at: "2026-02-16T10:30:00Z"
    artifacts:
      - docs/context/data-profile.md
      - docs/context/analyst-notes.md
  define_epics:
    status: completed
    completed_at: "2026-02-16T11:00:00Z"

epics:
  01-data-loading:
    status: completed
    pr: "#12"
    steps:
      step-01-read-csv:
        status: completed
        tests_pass: true
        review_approved: true
        commits: ["abc123", "def456"]
  02-data-translation:
    status: in_progress
    steps:
      step-01-column-renaming:
        status: completed
        tests_pass: true
        review_approved: true
      step-02-variable-grouping:
        status: completed
        tests_pass: true
        review_approved: true
      step-03-type-casting:
        status: in_progress
        tests_pass: null
        review_approved: null
```

## Agent Team Architecture

The harness uses Claude Code agent teams for the build/review loop.

### Roles

**Team Lead (Orchestrator)** — Delegate mode, coordination only
- Creates the team, populates shared task list from epic steps
- Manages `project-state.yaml` and `claude-progress.txt`
- Monitors circuit breaker state
- Advances to next epic when all steps approved
- Never writes implementation code directly

**Developer Teammate** — Implements steps
- Claims steps from the shared task list (one at a time)
- Implements, runs tests, self-reviews, commits with descriptive messages
- Emits structured status block after each step
- Receives feedback directly from reviewer (no relay through lead)
- Iterates on feedback until reviewer approves

**Reviewer Teammate** — Reviews work
- Monitors for completed developer tasks
- Reviews against: acceptance criteria, coding standards, test immutability, regressions
- Sends specific, actionable feedback directly to developer if changes needed
- Marks task as approved when satisfied

**Profiler Agent** (subagent, Phase 1 only)
- Runs PySpark exploration queries
- Generates structured data profile
- Surfaces data quality concerns

### Build/Review Loop

```
1. Lead populates task list with steps from epic spec
2. Developer claims step, implements it, commits
3. Developer emits structured status block
4. Developer marks step as complete
5. TaskCompleted hook runs:
   - Tests pass?
   - Lint clean?
   - Test files unmodified since TDD phase?
   - If hook fails -> task stays incomplete, developer gets feedback
6. Reviewer sees completed task -> reviews the diff
   - If changes needed -> messages developer directly with feedback
   - Developer fixes -> re-marks as complete -> reviewer re-reviews
7. Reviewer approves -> task fully complete
8. Developer claims next step -> repeat
```

### Structured Status Block

The developer agent must emit after each step:

```
STATUS: COMPLETE | IN_PROGRESS
TASKS_COMPLETED: <n>
FILES_MODIFIED: <n>
TESTS: PASS | FAIL | SKIP
WORK_TYPE: implementation | testing | documentation | refactoring
EXIT_SIGNAL: true | false
```

## Hooks and Mechanical Enforcement

### Hook Configuration

| Hook Event | Trigger | Action |
|---|---|---|
| `SessionStart` | Agent session begins | Read `project-state.yaml`, sync Claude Code tasks, show current phase and next action |
| `TaskCompleted` | Developer marks a task done | Run tests, check lint, validate test immutability, verify git changes. Exit code 2 blocks completion if any check fails |
| `TeammateIdle` | Reviewer or developer goes idle | Nudge to pick up next work or check for pending feedback |

### Enforcement Scripts

**`check-test-immutability.sh`** — Compares test files against TDD-phase commit. Blocks task completion if tests were modified during build.

**`definition-of-done.sh`** — Pre-PR checklist: all tests pass, lint clean, all steps reviewed, progress file updated, no TODOs or debug prints, state file current.

**`quality-scan.sh`** — Background scan for: coding standard deviations, unused imports, hand-rolled helpers, type annotation gaps at boundaries.

**`validate-config.py`** — Pre-flight: checks project config against actual data (column names exist, types compatible, predictor variables present).

## Error Handling and Self-Correction

### Layer 1: Developer Self-Correction

Developer agent attempts to fix issues before escalating:
- Test failures: read error, fix implementation, re-run
- Lint failures: auto-fix where possible, manual fix otherwise

### Layer 2: Review Agent Feedback Loop

If acceptance criteria not met:
- Reviewer sends specific feedback directly to developer
- Developer addresses each point, re-commits
- Reviewer re-reviews
- Max review rounds before escalation (configurable, default: 5)

### Layer 3: Circuit Breaker

Three-state system (CLOSED -> HALF_OPEN -> OPEN):

| Signal | Threshold (default) | Action |
|---|---|---|
| No file changes for N iterations | 3 | HALF_OPEN -> warn |
| Same error repeated | 5 | OPEN -> halt |
| Review loop exceeds max rounds | 5 | OPEN -> halt, escalate |
| Output quality declining | 70% decline | OPEN -> halt |
| Permission denial | 2 | OPEN -> halt |

### Layer 4: Human Escalation

When automated recovery fails:
- Orchestrator surfaces the issue with full context
- Provides: what was attempted, what failed, reviewer feedback, circuit breaker state
- Human decides: fix manually, provide guidance, skip the step, or re-plan

### Layer 5: Graceful Degradation

- State file marks the step as `blocked` with a reason
- Epic can't be submitted until all steps are `completed` or explicitly `skipped` by human
- No partial PRs

## Compound Learning System

Adapted from [Every Inc's compound engineering plugin](https://github.com/EveryInc/compound-engineering-plugin). Learnings from each step are captured, validated, and made searchable so that each feature makes the next feature easier to build.

### Pull-Based Architecture (not Push-Based)

Learnings are **searched on demand** (pull), not injected at session start (push). This scales to hundreds of solution docs without wasting context window on irrelevant knowledge.

| | Push (rejected) | Pull (adopted) |
|---|---|---|
| **When loaded** | Session start — injected upfront | On demand — searched during plan/build |
| **Context cost** | Pays upfront (wastes tokens on irrelevant items) | Pays only when relevant (targeted search) |
| **Scales to** | Degrades as learnings grow | Hundreds of docs (grep filters first) |
| **Agent** | Session-start hook | `learnings-researcher` agent |

### Two-Tier Knowledge Store

Knowledge lives at two levels: per-project and team-shared.

```
~/repos/
├── team-knowledge/                        # Shared repo — entire team contributes
│   └── docs/solutions/                    # Same structure as per-project
│       ├── data-quality-issues/
│       ├── model-library-issues/
│       ├── pyspark-issues/
│       ├── performance-issues/
│       ├── integration-issues/
│       ├── best-practices/
│       └── patterns/
│           └── critical-patterns.md       # Team-wide required reading
│
├── client-alpha-project/                  # Client project repo
│   └── docs/solutions/                    # Project-specific knowledge
│       ├── data-quality-issues/
│       ├── performance-issues/
│       └── patterns/
│           └── critical-patterns.md       # Project-specific required reading
```

The shared repo path is configured once per developer:

```yaml
# .harnessrc (per-project) or ~/.claude/settings.json (global)
shared_knowledge_path: "~/repos/team-knowledge"
```

### Solution Document Format

Every solution doc uses YAML frontmatter with a validated schema (adapted from Every's `compound-docs` skill):

```yaml
---
title: "Null handling in target column causes model library crash"
date: 2026-03-10
problem_type: runtime_error        # enum: data_quality_issue, runtime_error, performance_issue, etc.
component: model_library           # enum: data_loading, data_translation, model_execution, reporting, etc.
severity: critical                 # enum: critical, high, medium, low
root_cause: missing_null_check     # enum: missing_validation, type_mismatch, memory_overflow, etc.
resolution_type: code_fix          # enum: code_fix, config_change, workaround, documentation, etc.

applies_to:
  scope: universal                 # universal | conditional
  project_types: []                # empty = all types. e.g., [churn_modeling, pricing, segmentation]
  data_characteristics: []         # e.g., [large_dataset, sparse_nulls, categorical_heavy]
  tools: [custom_model_library]    # e.g., [pyspark, databricks, custom_model_library]

# Lifecycle metadata (for pruning)
status: active                     # active | deprecated | superseded
superseded_by: ""                  # path to replacement doc (if superseded)
last_validated: 2026-03-10         # last date this solution was confirmed still applicable
context:
  library_versions:                # version constraints — researcher skips if mismatch
    custom_model_library: ">=2.1"
  tool_versions:
    pyspark: ">=3.4"

tags: [null-handling, model-library, target-variable]
---

## Problem
[What happened]

## Symptoms
[Observable indicators]

## What Didn't Work
[Approaches tried and why they failed]

## Solution
[What fixed it, with code before/after]

## Why This Works
[Root cause explanation]

## Prevention
[How to avoid this in future]
```

### Project Profile for Relevance Matching

Each client project declares its characteristics so the learnings-researcher can filter:

```yaml
# .harnessrc
project_profile:
  project_types: [churn_modeling]
  data_characteristics: [large_dataset, sparse_nulls, categorical_heavy]
  model_types: [logistic_regression, gradient_boosting]
  industry: insurance
  tools: [pyspark, databricks, custom_model_library]
```

### Learnings Researcher Agent

A dedicated subagent invoked during `/plan-epic` and `/build` to search for relevant prior solutions. Uses a grep-first filtering strategy:

```
1. ALWAYS read:
   - Project: docs/solutions/patterns/critical-patterns.md
   - Team: <shared_path>/docs/solutions/patterns/critical-patterns.md
   - All docs with scope: universal

2. FILTER by project profile match:
   - project_types overlaps? Include.
   - data_characteristics overlaps? Include.
   - tools overlaps? Include.
   - No overlap on any dimension? Skip.

3. KEYWORD search within the filtered set for current task relevance

4. READ frontmatter only (first 30 lines) of candidates, score relevance

5. FULL READ only of truly relevant matches

6. RETURN distilled summary with key insights and recommendations
```

### Compound Step (Knowledge Capture)

After each step is built and reviewed, the developer writes a solution doc if something notable was learned. This replaces the simpler debrief protocol:

1. Agent detects a resolved problem (test failure fixed, workaround found, unexpected behavior handled)
2. Agent writes a solution doc to `docs/solutions/<category>/` with validated YAML frontmatter
3. `TaskCompleted` hook validates the frontmatter against the schema
4. At epic boundaries, agent asks: "Is this project-specific or team-wide?"
   - Project-specific → stays in `./docs/solutions/`
   - Team-wide → copied to the shared repo, committed, pushed (or PR'd)

### How the Flywheel Works

```
Project A: discovers "model library crashes on null target"
    → writes to project docs/solutions/
    → promoted to team-knowledge repo (scope: universal)

Project B (3 months later): starts planning model execution epic
    → learnings-researcher searches team-knowledge
    → finds "model library crashes on null target"
    → developer adds null check before calling library
    → avoids the bug entirely
```

Each project makes every future project easier.

### Self-Verification CLI Pattern

All enforcement scripts are callable by the developer agent as pre-checks, not just post-completion hooks:

```bash
# Self-check before marking a step complete:
pytest tests/ -v
bash <plugin_root>/hooks/check-test-immutability.sh tdd-baseline
bash <plugin_root>/hooks/self-check.sh <step> <epic>
```

This shifts from "gatekeeper catches you" to "developer checks itself first."

### Compaction as Implicit Review

In long agent team sessions, context window compaction forces the model to re-read code. This naturally serves as an additional review pass. The harness should not aggressively prevent compaction; it provides a free review opportunity.

### Knowledge Pruning

Solution docs go stale as tooling evolves, libraries update, and better fixes are discovered. Three mechanisms work together to keep the knowledge base current:

**Layer 1: Version-Gated Retrieval**

Solution docs carry version constraints in their frontmatter (`context.library_versions`, `context.tool_versions`). The learnings-researcher checks these against the current project's actual versions at retrieval time:

- **Version mismatch** → skip the doc entirely (don't surface outdated fixes)
- **`last_validated` older than threshold** (configurable, default: 90 days) → flag as potentially stale, surface with a warning rather than as a confident recommendation
- **`status: deprecated` or `superseded`** → skip entirely

This means stale docs are silently filtered out without manual cleanup.

**Layer 2: Contradiction-Based Auto-Deprecation**

When a new solution doc is written for the same `component` + `problem_type` + `root_cause` combination as an existing doc:

1. The harness detects the overlap during `validate-solution-doc.sh`
2. Surfaces the older doc to the developer: "An existing solution covers this same issue. Is the new one a replacement?"
3. If yes → old doc's `status` is set to `superseded`, `superseded_by` points to the new doc
4. If no → both remain active (different contexts or complementary solutions)

This handles the common case where fixes evolve over time without requiring a manual sweep.

**Layer 3: Scheduled Compaction Sweep (`/prune-knowledge`)**

A periodically-run skill that reviews all solution docs across both tiers:

| Check | Action |
|---|---|
| `status: deprecated` or `superseded` with `superseded_by` filled | Archive (move to `_archived/` subdirectory) |
| `last_validated` older than threshold | Surface to human: "Still valid?" → refresh date or deprecate |
| Version constraints that no longer match any active project profile | Flag as potentially obsolete |
| Duplicate `component` + `problem_type` + `root_cause` combinations | Surface for merge or supersession |
| Docs never retrieved by the learnings-researcher (if retrieval logging exists) | Flag as low-value candidates for review |

The sweep is non-destructive by default — it archives rather than deletes, and surfaces candidates to the human rather than auto-pruning. Archived docs move to `docs/solutions/_archived/` with a reason tag.

```
docs/solutions/
├── data-quality-issues/
│   ├── 2026-03-10-null-target-crash.md          # active
│   └── _archived/
│       └── 2026-02-20-null-target-workaround.md # superseded by 2026-03-10 version
```

## Execution Environment: Isolated VM

The harness is designed for fully autonomous operation. Claude Code runs with `--dangerously-skip-permissions` so the agent can execute code, run tests, commit, and create PRs without manual approval gates slowing the feedback loop.

**This requires an isolated VM** — not a developer's local machine. The VM provides:

- **Sandboxing:** Agent can't accidentally modify production systems, shared drives, or other projects
- **Reproducibility:** Clean environment for each project run (Docker + Databricks connectivity)
- **Safety:** `dangerouslySkipPermissions` is acceptable because the blast radius is limited to the VM
- **Cost control:** VM can be spun up/down per project engagement

### VM Requirements

| Component | Requirement |
|---|---|
| OS | Linux (Ubuntu 22.04+ recommended) |
| Docker | For local PySpark development container |
| Claude Code | Latest version with `--dangerously-skip-permissions` flag |
| Network | Outbound access to Databricks workspace, GitHub, Anthropic API |
| Git | Configured with deploy key for project repos |
| Databricks CLI | Authenticated to the team's workspace |
| Python | 3.10+ with project dependencies |

### Configuration

```yaml
# .harnessrc
execution:
  mode: autonomous                    # autonomous | interactive
  skip_permissions: true              # only valid on isolated VMs
  vm_id: ""                          # set by infrastructure provisioning
```

### Infrastructure Setup (TODO)

> **Note:** VM provisioning infrastructure is out of scope for the plugin itself, but must be built alongside it. Key decisions:
> - Cloud provider and VM sizing (on-demand vs. spot)
> - Provisioning automation (Terraform, Pulumi, or cloud-native)
> - Pre-baked VM image with all dependencies
> - Secure credential injection (Databricks token, GitHub deploy key, Anthropic API key)
> - VM lifecycle management (auto-shutdown after idle timeout)
> - Log collection and monitoring

## Databricks Integration: MCP Server + Skill

The agent needs to execute PySpark code on Databricks for scaled data processing. An MCP server wraps the Databricks REST API, and a skill teaches the agent when and how to use it.

### MCP Server: `databricks-executor`

A lightweight MCP server that exposes Databricks operations as tools:

| Tool | Description |
|---|---|
| `execute_code` | Run a code snippet on a Databricks cluster (blocking, returns output) |
| `upload_file` | Upload a local file to DBFS or Unity Catalog volume |
| `download_file` | Download a file from DBFS to local filesystem |
| `cluster_status` | Check if the configured cluster is running |
| `start_cluster` | Start the cluster if it's terminated |
| `list_tables` | List tables in a schema (for data discovery) |

### Configuration

```yaml
# .harnessrc
databricks:
  workspace_url: "https://adb-xxxx.azuredatabricks.net"
  cluster_id: "xxxx-xxxxxx-xxxxxxxx"
  default_catalog: "main"
  default_schema: "client_xyz"
  token_env_var: "DATABRICKS_TOKEN"     # read from environment, never stored in config
```

The MCP server reads config from `.harnessrc` and authenticates via the environment variable.

### Skill: `run-on-databricks`

Teaches the agent when to use local PySpark (small data, fast iteration) vs. Databricks (full dataset, production validation):

- **Local Docker:** Data profiling on samples, unit tests, development iteration
- **Databricks:** Full-scale data processing, integration tests against real data, production-grade validation
- The agent should develop locally first, then validate on Databricks before marking a step complete

### Plugin Structure Additions

```
one-shot-build/
├── mcp/
│   └── databricks-executor/
│       ├── server.py                  # MCP server implementation
│       ├── requirements.txt
│       └── README.md
├── skills/
│   └── run-on-databricks/SKILL.md    # When and how to use Databricks
```

## Kanban Dashboard

A local web dashboard that reads `project-state.yaml` and renders a visual Kanban board showing all epics, steps, and their statuses. The human uses this to monitor progress without needing to ask the agent or read YAML files.

### Architecture

A simple static HTML/JS application served locally. No backend needed — it reads `project-state.yaml` directly (via a tiny file-serving script or the browser's File API).

```
one-shot-build/
├── dashboard/
│   ├── index.html                    # Single-page Kanban app
│   ├── style.css
│   ├── app.js                        # YAML parsing + board rendering
│   ├── serve.sh                      # Local server script (python -m http.server)
│   └── package.json                  # js-yaml dependency for YAML parsing
```

### Board Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  One-Shot Build — Client XYZ Churn Model                           │
│  Phase: Build  |  Epic: 02-data-translation  |  Step: step-03      │
├──────────┬──────────┬──────────┬──────────┬──────────┬─────────────┤
│ Pending  │ Planning │ Building │ Review   │ Complete │ Blocked     │
├──────────┼──────────┼──────────┼──────────┼──────────┼─────────────┤
│ epic-03  │          │ step-03  │          │ epic-01  │             │
│ epic-04  │          │ type-    │          │ step-01  │             │
│          │          │ casting  │          │ step-02  │             │
│          │          │          │          │ col-     │             │
│          │          │          │          │ rename   │             │
└──────────┴──────────┴──────────┴──────────┴──────────┴─────────────┘

Filters: [All Epics ▾] [All Statuses ▾] [Show Steps ☑]
```

### Features

- **Auto-refresh:** Watches `project-state.yaml` for changes (via polling or filesystem events)
- **Epic-level view:** Shows epics as cards across status columns
- **Step drill-down:** Click an epic to see its steps as sub-cards
- **Filters:**
  - By epic (dropdown)
  - By status (pending, in_progress, completed, blocked)
  - By gate (tests_pass, review_approved)
  - Toggle step visibility
- **Color coding:**
  - Green: completed (both gates pass)
  - Blue: in progress
  - Yellow: review pending (tests pass, awaiting review)
  - Red: blocked or circuit breaker OPEN
  - Gray: pending
- **Summary bar:** Overall progress percentage, circuit breaker state, current phase

### Launch

```bash
# From the project root:
bash <plugin_root>/dashboard/serve.sh
# Opens http://localhost:8080 in the browser
```

Or via command: `/board` opens the dashboard.

## Consolidated Practices (37 Total)

| # | Practice | Enforcement |
|---|---|---|
| 1 | Session boot protocol | `SessionStart` hook |
| 2 | Commit discipline | Developer prompt + review criteria |
| 3 | State file in YAML | Template (`/init`) |
| 4 | Progress file (`claude-progress.txt`) | Developer prompt + state update scripts |
| 5 | One step at a time | Task list dependencies + developer prompt |
| 6 | Production quality at every commit | Review agent criteria |
| 7 | Progressive disclosure (~100-line CLAUDE.md) | Template (`/init`) |
| 8 | Lightweight and rippable | Plugin architecture (modular skills) |
| 9 | Continuous automated refactoring | `/quality-scan` skill |
| 10 | CLAUDE.md as table of contents | Template (`/init`) |
| 11 | Mechanical taste enforcement | Linters + formatters in `TaskCompleted` hook |
| 12 | Definition of done checklist | `definition-of-done.sh` in `/submit` skill |
| 13 | Self-review before external review | Developer prompt instructions |
| 14 | Background quality scanning | `/quality-scan` skill |
| 15 | Shared utilities over hand-rolled | Review agent criteria |
| 16 | Typed boundaries, no YOLO data probing | Review agent criteria + pre-flight validation |
| 17 | Test immutability during build | `check-test-immutability.sh` in `TaskCompleted` hook |
| 18 | Circuit breaker pattern | Orchestrator monitoring logic |
| 19 | Structured status block | Developer prompt contract |
| 20 | Dual-condition exit gate | Orchestrator + `TaskCompleted` hook |
| 21 | Git-based progress detection | Circuit breaker + `TaskCompleted` hook |
| 22 | Anti-pattern prohibitions | Developer and reviewer prompts |
| 23 | Stuck loop detection | Circuit breaker (error history comparison) |
| 24 | Separated prompt architecture | Epic spec + task list + coding standards |
| 25 | Per-project config overrides (`.harnessrc`) | Plugin reads project-local config |
| 26 | Rate limiting | Orchestrator monitoring logic |
| 27 | Compound learning system (pull-based) | `learnings-researcher` agent searches `docs/solutions/` + shared team repo on demand during plan/build |
| 28 | Solution document schema | YAML frontmatter with validated enums (problem_type, component, severity, applies_to) on every solution doc |
| 29 | Cross-project knowledge transfer | Two-tier store: per-project `docs/solutions/` + shared `team-knowledge` repo with profile-based relevance matching |
| 30 | Self-verification CLI pattern | Enforcement scripts callable by developer as pre-checks, not just post-hooks |
| 31 | Compaction as implicit review | Long sessions benefit from natural re-read during context compaction |
| 32 | Version-gated retrieval | Learnings-researcher skips docs with mismatched version constraints or stale `last_validated` dates |
| 33 | Contradiction-based auto-deprecation | `validate-solution-doc.sh` detects overlapping `component+problem_type+root_cause` and prompts for supersession |
| 34 | Scheduled knowledge compaction | `/prune-knowledge` skill archives deprecated docs, flags stale docs, surfaces merge candidates |
| 35 | Isolated VM execution | `dangerouslySkipPermissions` on sandboxed VM only — never on developer machines |
| 36 | Databricks MCP integration | MCP server for remote code execution, file transfer, cluster management on Databricks |
| 37 | Visual Kanban dashboard | Local web app reads `project-state.yaml` and renders filterable board with auto-refresh |

## References

- [OpenAI: Harness Engineering](https://openai.com/index/harness-engineering/) — Repository as system of record, progressive disclosure, mechanical enforcement, agent-to-agent review
- [Anthropic: Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — Session boot protocol, progress files, feature lists in JSON, two-phase architecture
- [Phil Schmid: The Importance of Agent Harness in 2026](https://www.philschmid.de/agent-harness-2026) — Lightweight and modular design, context engineering, structured trajectory capture
- [Claude Code: Agent Teams](https://code.claude.com/docs/en/agent-teams) — Agent team architecture, shared task lists, direct teammate communication
- [Claude Code: Tasks](https://x.com/trq212/status/2014480496013803643) — Task system for cross-session coordination
- [Ralph Loop (frankbria/ralph-claude-code)](https://github.com/frankbria/ralph-claude-code) — Circuit breaker, structured status blocks, dual-condition exit gate, stuck loop detection
- [Peter Steinberger: Shipping at Inference Speed](https://steipete.me/posts/2025/shipping-at-inference-speed) — Agent-discoverable docs, cross-project knowledge, self-verification CLI, compaction as review
- [Every Inc: Compound Engineering](https://every.to/chain-of-thought/compound-engineering-how-every-codes-with-agents) — Pull-based knowledge retrieval, structured YAML schema with enum validation, category-based solution docs, learnings-researcher agent pattern
