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
│   └── harness-status/SKILL.md        # Check workflow state, show next action
├── hooks/
│   ├── hooks.json                     # Hook config (SessionStart, TaskCompleted, TeammateIdle)
│   ├── session-start.sh               # Read state file, sync tasks, show current phase
│   ├── check-test-immutability.sh     # Detect unauthorized test modifications during build
│   └── definition-of-done.sh          # Pre-PR quality checklist
├── commands/
│   ├── init.md                        # /init shorthand
│   ├── status.md                      # /status shorthand
│   └── next.md                        # /next — advance to next step
├── agents/
│   ├── reviewer.md                    # Review agent: separate prompt, critical evaluation
│   └── profiler.md                    # Data profiling agent for context gathering
├── templates/                         # Scaffolding templates for new projects
│   ├── CLAUDE.md.template
│   ├── project-state.yaml.template
│   ├── definition-of-done.md.template
│   ├── review-criteria.md.template
│   ├── coding-standards.md.template
│   └── .harnessrc.template
└── lib/
    └── state.sh                       # Utilities for reading/updating project-state.yaml
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
│   └── plans/                         # Implementation plans per epic
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

## Agent Debrief Protocol

Learnings from each agent must be captured and propagated to prevent knowledge loss across agent boundaries and sessions.

### Debrief Log (`docs/context/debrief-log.yaml`)

After every step, both the developer and reviewer agents append a structured entry:

```yaml
- step: "step-03-type-casting"
  epic: "02-data-translation"
  agent: "developer"
  timestamp: "2026-02-16T14:30:00Z"

  what_worked:
    - "Using .cast() with StringType() before joining avoided mixed-type errors"

  what_failed:
    - approach: "Direct integer cast on column 'zip_code'"
      why: "Some zip codes have leading zeros — must stay as strings"

  discoveries:
    - "Column 'region' has 47 unique values, not 50 — 3 states missing from source data"

  decisions:
    - "Used left join instead of inner join to preserve rows with missing region mapping"
      reason: "Analyst notes say missing regions should be flagged, not dropped"
```

Reviewer entries capture review-specific insights:

```yaml
- step: "step-03-type-casting"
  agent: "reviewer"
  timestamp: "2026-02-16T14:45:00Z"

  review_notes:
    - "Developer initially missed null handling in cast — caught on first review round"

  patterns_to_watch:
    - "This codebase tends to skip null checks after joins — always verify"
```

### How Learnings Propagate

| Mechanism | Scope | When |
|---|---|---|
| Agent team messaging | Within current session | Real-time during build/review |
| Topic-based learnings files | Across sessions | Read by agents based on current work context |
| Orchestrator spawn prompts | Into new teammates | Relevant prior debriefs included when spawning developer/reviewer |
| `CLAUDE.md` distillation | Permanent project knowledge | At epic boundaries, orchestrator distills recurring learnings into CLAUDE.md |
| Plugin-level knowledge base | Across all client projects | Non-project-specific learnings promoted to plugin's `knowledge/` directory |

### Agent-Discoverable Documentation

Instead of one monolithic `debrief-log.yaml`, learnings are organized into topic-based files with descriptive names that agents can self-select based on their current work:

```
docs/context/learnings/
├── data-quirks.md            # Agent finds this when working on data loading/translation
├── model-library-notes.md    # Agent finds this when interfacing with the custom library
├── pyspark-gotchas.md        # Agent finds this for PySpark-specific issues
├── failed-approaches.md      # Agent finds this when stuck or exploring alternatives
└── debrief-log.yaml          # Full structured debrief log (append-only)
```

The `debrief-log.yaml` remains the canonical structured log. Topic-based files are distilled summaries organized for discoverability. Agents browse `docs/context/learnings/` and pick what's relevant based on filenames — they are not told which file to read.

### Cross-Project Knowledge Transfer

Learnings that are not specific to a single client project (e.g., "the custom model library requires DataFrames with no null values in the target column") are promoted to a **plugin-level knowledge base**:

```
one-shot-build/                  # The plugin repo
├── knowledge/
│   ├── model-library.md         # Learnings about the in-house modeling library
│   ├── pyspark-patterns.md      # PySpark patterns that work across projects
│   └── common-pitfalls.md       # Mistakes that keep recurring across projects
```

At epic boundaries, the orchestrator reviews debrief entries and identifies learnings that are reusable. These are promoted (via PR to the plugin repo) to `knowledge/`. The `SessionStart` hook includes relevant plugin knowledge in the injected context.

This creates a **flywheel**: each client project makes the harness smarter for the next one.

### Self-Verification CLI Pattern

All enforcement scripts are designed to be callable by the developer agent as pre-checks, not just as post-completion hooks. Before marking a task complete, the developer should run:

```bash
# Self-check: tests pass?
pytest tests/ -v

# Self-check: test immutability?
bash <plugin_root>/hooks/check-test-immutability.sh tdd-baseline

# Self-check: debrief written?
bash <plugin_root>/hooks/check-debrief.sh <step> <epic>
```

This shifts enforcement from "gatekeeper catches you after the fact" to "developer verifies itself first" — reducing rejected review cycles and reinforcing Practice #13 (self-review).

### Compaction as Implicit Review

In long agent team sessions, context window compaction forces the model to re-read code. This naturally serves as an additional review pass — the model often catches bugs during re-reading. This is a beneficial side effect of long sessions, not something to fight. The harness should not aggressively prevent compaction; it provides a free review opportunity.

### Enforcement

The `TaskCompleted` hook verifies that a debrief entry exists for the step being completed. No debrief = task cannot be marked done.

## Consolidated Practices (31 Total)

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
| 27 | Agent debrief protocol | `debrief-log.yaml` + `TaskCompleted` hook + session-start injection |
| 28 | Agent-discoverable documentation | Topic-based learnings files with descriptive names in `docs/context/learnings/` |
| 29 | Cross-project knowledge transfer | Plugin-level `knowledge/` directory, promoted via PR at epic boundaries |
| 30 | Self-verification CLI pattern | Enforcement scripts callable by developer as pre-checks, not just post-hooks |
| 31 | Compaction as implicit review | Long sessions benefit from natural re-read during context compaction |

## References

- [OpenAI: Harness Engineering](https://openai.com/index/harness-engineering/) — Repository as system of record, progressive disclosure, mechanical enforcement, agent-to-agent review
- [Anthropic: Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — Session boot protocol, progress files, feature lists in JSON, two-phase architecture
- [Phil Schmid: The Importance of Agent Harness in 2026](https://www.philschmid.de/agent-harness-2026) — Lightweight and modular design, context engineering, structured trajectory capture
- [Claude Code: Agent Teams](https://code.claude.com/docs/en/agent-teams) — Agent team architecture, shared task lists, direct teammate communication
- [Claude Code: Tasks](https://x.com/trq212/status/2014480496013803643) — Task system for cross-session coordination
- [Ralph Loop (frankbria/ralph-claude-code)](https://github.com/frankbria/ralph-claude-code) — Circuit breaker, structured status blocks, dual-condition exit gate, stuck loop detection
- [Peter Steinberger: Shipping at Inference Speed](https://steipete.me/posts/2025/shipping-at-inference-speed) — Agent-discoverable docs, cross-project knowledge, self-verification CLI, compaction as review
