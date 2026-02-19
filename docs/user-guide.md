# One-Shot Build User Guide

Step-by-step instructions for using the one-shot-build harness to execute a client analytics project with Claude Code.

## Prerequisites

Before you begin, make sure you have:

- **Claude Code** installed and authenticated
- **The one-shot-build plugin** installed:
  ```bash
  claude plugins install <path-to-plugin-repo>
  ```
- **yq** installed (`brew install yq` or `apt install yq`) for YAML processing
- **Python 3.10+** for your project code
- **Team knowledge repo** (optional) cloned locally for cross-project learnings:
  ```bash
  git clone <team-knowledge-repo-url> ~/repos/team-knowledge
  ```
  Then set `shared_knowledge_path` in your project's `kyros-agent-workflow/.harnessrc` to point to it.
- **Docker** (optional) if running PySpark locally
- **Databricks CLI** (optional) if executing on a Databricks cluster

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/init` | Scaffold a new project |
| `/status` | Show where you are and what to do |
| `/profile-data [paths]` | Profile data tables |
| `/define-epics [context-files]` | Collaboratively break the project into epics |
| `/execute-plan <build-dir>` | Execute epics interactively (plan, build, submit loop) |
| `/execute-plan-autonomously <build-dir>` | Execute epics with minimal human intervention |
| `/board` | Open the Kanban dashboard in your browser |
| `/prune-knowledge` | Clean up old solution docs |

You can always type `/status` to see your current phase and suggested next action.

---

## Step 1: Create Your Project

Start in an empty directory (or an existing repo where you want to add the harness).

```
/init
```

The harness will ask for your project name, then create the full project structure:

- `CLAUDE.md` — the project guide that Claude reads on every session (lives at the project root)
- `kyros-agent-workflow/.harnessrc` — project-specific configuration (edit this later for Databricks, team knowledge, etc.)
- `kyros-agent-workflow/docs/standards/` — coding standards, definition of done, review criteria
- `kyros-agent-workflow/docs/solutions/` — where learnings accumulate as you work

> **Note:** All project files live inside the `kyros-agent-workflow/` directory, with `CLAUDE.md` being the only file at the project root. Execution state is tracked per build directory in `.execution-state.yaml`, created when you run `/execute-plan`.

---

## Step 2: Profile Your Data

```
/profile-data
```

You can optionally pass data file paths as arguments (e.g., `/profile-data data/customers.parquet data/transactions.csv`). If you don't, the harness will ask where your data lives.

The harness will:

1. **Determine which tables to profile** — from your arguments or by asking
2. **Check for existing profiles** — if a profile already exists for a table, asks whether to overwrite it or create a new version (saved as `data-profile-<table>-v<N>.md`)
3. **Profile each table** — dispatches a profiler sub-agent that generates a detailed report covering column types, distributions, null counts, unique values, min/max, and data quality issues
4. **Present summaries** — shows you a brief summary of each profiled table: row/column counts, key quality concerns, and notable patterns
5. **Commit** — commits the profile files to git

**What you'll decide:** Which tables to profile, and whether to overwrite or version any existing profiles.

**What gets created:**
- `kyros-agent-workflow/docs/context/data-profile-<table>.md` — structured data exploration (one per table)

---

## Step 3: Define Your Epics

```
/define-epics
```

You can optionally pass context files as arguments (e.g., `/define-epics kyros-agent-workflow/docs/context/data-profile-customers.md`).

The harness will:

1. **Ask what you want to build** — do you already have epics in mind, or would you like it to search the knowledge base for similar past projects as inspiration?
2. **Propose an epic breakdown** — based on your input (or learnings from past projects), propose a sequence of work chunks (e.g., Data Loading, Data Translation, Model Execution, Report Generation)
3. **Refine with you** — ask whether epics should be split, combined, reordered, or if any are missing
4. **Ask you to name the build** — you choose a name (e.g., `v1`, `initial-model`), and specs are saved to `kyros-agent-workflow/builds/<name>/epic-specs/`
5. **Write epic specs** — each epic gets a YAML spec with acceptance criteria and dependency info

**What you'll decide:** Shape the epic breakdown to match how you think about the project. This is the most important planning step — get it right here and everything downstream flows smoothly.

**What gets created:**
- `kyros-agent-workflow/builds/<name>/epic-specs/01-name.yaml`, `02-name.yaml`, etc. — one spec per epic

---

## Step 4: Execute Your Epics

This is where the bulk of the work happens. The `/execute-plan` command orchestrates the full plan/build/submit cycle for every epic in your build directory.

### Choose your execution mode

**Interactive mode** (recommended for first use):
```
/execute-plan <build-dir>
```
Pauses at key checkpoints for your approval: after planning, after building, and after creating a PR. You stay in control.

**Autonomous mode** (for VM execution):
```
/execute-plan-autonomously <build-dir>
```
Runs the full cycle end-to-end with minimal human intervention. Auto-merges PRs and advances to the next epic automatically. Best used on an isolated VM with `--dangerously-skip-permissions`.

### Startup checks

Before execution begins, the orchestrator will:

1. **Verify the build directory** — confirms it exists and `epic-specs/` contains `.yaml` epic specs
2. **Check for concurrent executions** — warns if other executions are already in progress (risk of merge conflicts)
3. **Check context usage** — recommends clearing context if the session has significant prior conversation
4. **Check permissions** (autonomous only) — verifies `--dangerously-skip-permissions` is active
5. **Check for previous state** — if a prior execution was interrupted, offers to resume or start fresh

### The epic loop

For each epic, the orchestrator runs three phases:

#### Phase A: Plan

The orchestrator dispatches a **plan-epic sub-agent** that:

1. **Creates an epic branch** — `epic/<name>`
2. **Searches for prior solutions** — a learnings-researcher agent checks your knowledge base (and team knowledge, if configured) for relevant patterns
3. **Breaks the epic into testable steps** — each step is one focused unit of work with clear acceptance criteria
4. **Writes tests first (TDD)** — tests are written before any implementation code. They will all fail at this point — that's intentional.
5. **Tags the test baseline** — `tdd-baseline-<epic-name>` git tag locks the tests
6. **Creates an implementation plan** — step-by-step instructions for what to build

**Important:** The tests written here are locked. They cannot be modified during the build phase. This ensures the agent builds code that meets the original spec, not code that passes weakened tests.

**Interactive mode:** The orchestrator pauses here and asks "Ready to start building?" You can review the plan first or stop.

#### Phase B: Build

The orchestrator dispatches a **build-step coordinator** that manages the implementation of all steps within the epic. Unlike the planning and submit phases, the build phase spawns multiple sub-agents — a fresh developer and reviewer for each step.

**Per-step agent cycle:**

For each step in the implementation plan, the coordinator:

1. **Extracts the step context** from the plan file — the specific section with files, test commands, and implementation instructions
2. **Dispatches a developer sub-agent** with just that step's context, coding standards, and the TDD baseline tag. The developer implements the code, runs tests, self-reviews, and commits.
3. **Dispatches a reviewer sub-agent** with the git diff for that step, review criteria, and acceptance criteria. The reviewer runs the test suite, checks test immutability, and evaluates the diff.

```
Coordinator (build-step)
    |
    +- Step 1 ─── Developer ─── Reviewer ─── Approved ✓
    |              (torn down)   (torn down)
    |
    +- Step 2 ─── Developer ─── Reviewer ─── Changes requested
    |              (torn down)   (torn down)
    |                  |
    |              New Developer ── Reviewer ─── Approved ✓
    |              (torn down)      (torn down)
    |
    +- Step 3 ─── Developer ─── Reviewer ─── Approved ✓
    |              (torn down)   (torn down)
    ...
```

Each developer and reviewer agent gets a **clean context window** focused entirely on one step. This prevents context saturation on large epics — the developer working on step 5 isn't burdened by the accumulated context of steps 1-4.

**The review loop:**

When the reviewer requests changes, the coordinator spawns a **new developer agent** with the reviewer's specific feedback. The new developer has a fresh context containing only the step instructions and the feedback — no accumulated frustration from prior attempts. The reviewer then re-reviews. This loop repeats up to 5 rounds per step before the circuit breaker triggers.

**Circuit breaker monitoring:**

The coordinator watches for stuck loops:

| Signal | Threshold | What happens |
|--------|-----------|--------------|
| No file changes | 3 developer dispatches | Coordinator warns the next developer to try a different approach |
| Same error repeated | 5 times | Circuit breaker triggers (see replanning below) |
| Review rounds exceeded | 5 rounds | Circuit breaker triggers (see replanning below) |

**Replanning escalation (autonomous mode only):**

When the circuit breaker triggers due to persistent test failures, the coordinator can dispatch a **replanning agent** before halting. The replanning agent:

1. Analyzes why the tests can't be passed — is the implementation wrong, or are the tests wrong?
2. If the tests are correct: suggests a different implementation approach for the developer to try
3. If the tests are genuinely wrong: proposes specific test corrections with justification, applies them, creates a new TDD baseline tag (`tdd-baseline-<epic-name>-v2`), and logs the change prominently

This is a controlled release valve — it preserves test immutability as the default while giving autonomous mode a way forward when the plan was genuinely wrong. Only one replanning escalation is allowed per step; if it doesn't resolve the issue, the pipeline halts for human intervention.

In interactive mode, the circuit breaker always escalates to you directly — no automatic replanning.

**Step-level state tracking:**

Progress is tracked per step in `.execution-state.yaml`, so a resumed session picks up at the exact step that was interrupted — not from the beginning of the epic.

**What happens in the background:**
- Each developer agent searches project and team solution docs for relevant patterns before starting implementation. This means knowledge captured during earlier epics (or from other projects via the shared knowledge repo) is available to developers working on later steps — even though each developer agent starts with a fresh context.
- Solution docs are written automatically when a developer resolves tricky problems. These accumulate in `kyros-agent-workflow/docs/solutions/` as your project's knowledge base.
- The reviewer validates that any new solution docs have correct YAML frontmatter.

#### Phase C: Submit

The orchestrator dispatches a **submit-epic sub-agent** that:

1. **Runs the Definition of Done** — automated checks that all tests pass, no TODO comments or debug prints remain, test immutability is verified, and `<build-dir>/claude-progress.txt` is up to date
2. **Runs a quality scan** — checks for coding standard deviations, unused imports, missing type hints, and other drift
3. **Promotes learnings** — if you have a shared team knowledge repo configured, universal solutions are offered for promotion
4. **Creates a Pull Request** — pushes the epic branch and creates a PR with a summary of work, test results, and quality findings

**How failures are handled:**

| | Interactive mode | Autonomous mode |
|---|---|---|
| **DoD failures (superficial)** | Blocking — shows which checks failed, asks how to proceed | Auto-fix — removes TODOs, debug prints, re-runs checks (up to 3 attempts) |
| **DoD failures (code-level)** | Blocking — shows which tests failed, asks how to proceed | Re-dispatches the build-step agent with the failure context to fix the code, then re-runs submit (up to 2 retries before halting) |
| **Quality scan** | Non-blocking — flagged in PR description | Auto-fix where possible — imports, formatting committed; rest noted in PR |

**After the PR:**

- **Interactive mode:** The orchestrator tells you the PR was created and asks you to merge it. Once confirmed, it continues to the next epic.
- **Autonomous mode:** The sub-agent auto-merges the PR and the orchestrator immediately continues to the next epic.

### Between epics

**Interactive mode:** The orchestrator asks "Completed N of M epics. Next up: '<next-epic>'. Proceed?"

**Autonomous mode:** Continues immediately.

### Completion

When all epics are done:

- **Interactive mode:** Shows a summary of all PRs created
- **Autonomous mode:** Logs completion to `<build-dir>/claude-progress.txt`

---

## Monitoring Progress

### Check status anytime

```
/status
```

Shows your current phase, epic, step, test/review gates, and what to do next.

### Open the Kanban dashboard

```
/board
```

Opens a browser-based dashboard at `http://localhost:8080` showing all epics and steps as cards on a Kanban board. Filters by epic, status, and gate state. Auto-refreshes every 5 seconds.

---

## Agents and Sub-Agents

This section documents every agent the harness creates, who creates it, and when it is torn down. Agents are created via Claude Code's Task tool; each runs in its own context window and loses all memory when torn down. Continuity between agents flows only through files (plans, tests, state YAML, solution docs, progress logs).

### Step 2: Profile Data (`/profile-data`)

| Agent | Created by | Purpose | Torn down |
|-------|-----------|---------|-----------|
| **Profiler** | `/profile-data` | Profiles a single data table and writes a `data-profile-<table>.md` report | After each table's profile is written |

One profiler agent is dispatched per table, sequentially. Each is torn down before the next starts.

### Step 3: Define Epics (`/define-epics`)

| Agent | Created by | Purpose | Torn down |
|-------|-----------|---------|-----------|
| **Learnings-researcher** | `/define-epics` | Searches the shared knowledge base for similar past projects to inform the epic breakdown | After returning findings |

This agent is only created if a shared knowledge repo is configured in `.harnessrc` and the user opts in. `/define-epics` itself runs in the main session — it is not a sub-agent.

### Step 4: Execute Plan (`/execute-plan`)

The execute-plan orchestrator runs in the main session for the entire execution. It dispatches sub-agents for each phase of each epic.

#### Phase A: Plan

| Agent | Created by | Purpose | Torn down |
|-------|-----------|---------|-----------|
| **Plan-epic** | Orchestrator | Creates the epic branch, breaks the epic into steps, writes TDD tests, tags the test baseline, writes the implementation plan | After reporting "planning complete" |
| **Learnings-researcher** | Plan-epic | Searches local and shared knowledge base for patterns relevant to this epic | After returning findings to plan-epic |

The learnings-researcher is nested inside plan-epic — it is created and torn down within the plan-epic agent's lifetime. When plan-epic is torn down, its understanding of the epic (why tests were designed a certain way, trade-offs considered) is lost. Only the written plan and tests survive into the build phase.

#### Phase B: Build

| Agent | Created by | Purpose | Torn down |
|-------|-----------|---------|-----------|
| **Build-step (coordinator)** | Orchestrator | Loops through steps, dispatches developer/reviewer per step, monitors circuit breakers, updates step-level state | After all steps pass review, or circuit breaker trips |
| **Developer** (per step) | Build-step coordinator | Implements code for one step, runs tests, self-reviews, commits | After completing that step's implementation |
| **Reviewer** (per step) | Build-step coordinator | Reviews one step's diff against review criteria, verifies tests pass, checks test immutability | After returning review verdict for that step |
| **Developer** (fix round) | Build-step coordinator | Fixes specific reviewer feedback for one step | After committing fixes |
| **Replanning agent** | Build-step coordinator (autonomous mode only) | Analyzes persistent test failures, proposes test corrections or alternative approaches | After returning verdict |

Each step gets a fresh developer and reviewer — they do not carry context from previous steps. If the reviewer requests changes, a new developer agent is spawned with the feedback. The replanning agent is only dispatched when the circuit breaker trips in autonomous mode.

#### Phase C: Submit

| Agent | Created by | Purpose | Torn down |
|-------|-----------|---------|-----------|
| **Submit-epic** | Orchestrator | Runs Definition of Done, quality scan, promotes learnings, creates PR (and auto-merges in autonomous mode) | After reporting PR created/merged |

If submit-epic reports a code-level DoD failure in autonomous mode, the orchestrator re-dispatches a **build-step** agent to fix the issue, then re-dispatches **submit-epic**. This retry loop runs up to 2 times before halting. Each re-dispatched agent is a fresh instance with no memory of prior attempts — the failure context is passed explicitly by the orchestrator.

#### Lifecycle summary

```
/execute-plan <build-dir>
│
├─ Epic 1
│  ├─ Plan-epic ──────────────── created ──── torn down
│  │  └─ Learnings-researcher ─── created ─ torn down
│  │
│  ├─ Build-step (coordinator) ── created ──────────────────────────── torn down
│  │  ├─ Step 1: Developer ────── created ── torn down
│  │  │          Reviewer ─────── created ── torn down
│  │  ├─ Step 2: Developer ────── created ── torn down
│  │  │          Reviewer ─────── created ── torn down  (changes requested)
│  │  │          Developer ────── created ── torn down  (fix round)
│  │  │          Reviewer ─────── created ── torn down  (approved)
│  │  ├─ Step 3: Developer ────── created ── torn down
│  │  │          Reviewer ─────── created ── torn down
│  │  ...
│  │
│  └─ Submit-epic ────────────── created ──── torn down
│
├─ Epic 2 (fresh instances of everything)
│  ...
│
Orchestrator ───────────────────── lives for entire execution ─────────
```

No agent carries context between steps or between epics. Each developer and reviewer starts fresh. All continuity flows through files: the implementation plan, committed code, execution state YAML, solution docs, and progress logs.

---

## Configuring Your Project

Edit `kyros-agent-workflow/.harnessrc` in your project to customize behavior.

### Circuit breaker thresholds

Tune when the harness halts stuck loops:

```yaml
circuit_breaker:
  no_progress_threshold: 3
  same_error_threshold: 5
  max_review_rounds: 5
```

### Agent configuration

Choose which models the developer, reviewer, and replanning agents use:

```yaml
agent:
  developer_model: "sonnet"
  reviewer_model: "sonnet"
  replanning_model: "sonnet"
```

### Testing commands

Configure how the harness runs tests and linters:

```yaml
testing:
  test_command: "pytest kyros-agent-workflow/tests/ -v"
  lint_command: "ruff check kyros-agent-workflow/src/ kyros-agent-workflow/tests/"
  format_command: "ruff format kyros-agent-workflow/src/ kyros-agent-workflow/tests/"
```

### Team knowledge sharing

If your team has a shared knowledge repo, point to it so the learnings-researcher can search past solutions across all projects:

```yaml
shared_knowledge_path: "~/repos/team-knowledge"
```

### Project profile

Help the learnings-researcher find the most relevant prior solutions by describing your project:

```yaml
project_profile:
  project_types: [churn_modeling]
  data_characteristics: [large_dataset, sparse_nulls]
  model_types: [logistic_regression, gradient_boosting]
  industry: insurance
  tools: [pyspark, databricks, custom_model_library]
```

### Databricks integration

If your project uses Databricks for scaled execution:

```yaml
databricks:
  workspace_url: "https://adb-xxxx.azuredatabricks.net"
  cluster_id: "xxxx-xxxxxx-xxxxxxxx"
  default_catalog: "main"
  default_schema: "client_xyz"
  token_env_var: "DATABRICKS_TOKEN"
```

Then set the environment variable:
```bash
export DATABRICKS_TOKEN="your-token"
```

### Knowledge pruning

Control how aggressively stale solution docs are flagged:

```yaml
pruning:
  staleness_threshold_days: 90
  auto_archive_superseded: true
```

---

## Running on Databricks

During the build phase, most development and testing happens locally (or in Docker). Use Databricks when you need to:

- Process datasets larger than 1GB
- Run integration tests against real data
- Validate code before a production PR
- Access Unity Catalog tables

The harness will guide you through Databricks execution when relevant, or you can invoke it directly by asking Claude to use the `run-on-databricks` skill.

---

## Maintaining Your Knowledge Base

Over time, solution docs accumulate in `kyros-agent-workflow/docs/solutions/`. Run the pruning command periodically to keep them healthy:

```
/prune-knowledge
```

This will:
- Archive superseded solutions
- Flag stale docs for your review (refresh, deprecate, or skip)
- Detect duplicate solutions
- Check version compatibility with your current project

---

## Autonomous Execution on a VM

For fully hands-off execution, run on an isolated VM with `--dangerously-skip-permissions` mode. See `docs/infrastructure/vm-setup.md` for setup instructions.

**Never run in autonomous mode on your local machine.**

The autonomous workflow:

1. Set up the VM and install Claude Code (see `docs/infrastructure/vm-setup.md`)
2. Run `/init`, `/profile-data`, and `/define-epics` interactively to set up the project and approve the epic breakdown
3. Start autonomous execution:
   ```bash
   claude --dangerously-skip-permissions
   ```
   Then run:
   ```
   /execute-plan-autonomously <build-dir>
   ```
4. The harness runs the full plan/build/submit loop for every epic, auto-merging PRs along the way

The entire project executes end-to-end:
```
Plan -> Build -> Submit -> Plan -> Build -> Submit -> ... -> Done
```

---

## Troubleshooting

**"No harness project found"**
You're not in a harness project directory. Navigate to the correct project root (where the `kyros-agent-workflow/` directory exists) or run `/init` to start a new project.

**Circuit breaker triggered**
The harness stops when it detects the agent is stuck (same error 5+ times, no progress for 3+ iterations, or 5+ review rounds). Read the error context, decide whether to adjust the approach, and resume with `/execute-plan <build-dir>` (it will offer to resume from where it left off).

**Tests failing after plan phase**
That's expected. The plan phase writes tests that intentionally fail — they define what the code should do before it exists. The build phase makes them pass.

**Reviewer keeps requesting changes**
Check the review feedback. Common causes: missing acceptance criteria, coding standard violations, or regressions in other tests. The harness escalates to you after 5 review rounds.

**Replanning triggered (autonomous mode)**
The replanning agent was dispatched because the circuit breaker tripped on persistent test failures. Check `<build-dir>/claude-progress.txt` for the `REPLAN:` log entry, which includes the justification for any test changes. A new TDD baseline tag (`tdd-baseline-<epic-name>-v2`) was created. If you disagree with the test changes, revert the commit and re-run the build interactively.

**Build resumed at wrong step**
If the build seems to be re-doing completed work, check `.execution-state.yaml` for the step-level status. Steps marked `completed` will be skipped. If step state is missing or corrupt, delete the `steps:` block for that epic and re-run — the coordinator will re-initialize steps from the plan.

**Dashboard not loading**
Make sure you're running `/board` from within a project directory that has an active execution. The dashboard reads `.execution-state.yaml` to render the board.

**Concurrent execution warning**
If you see a warning about other active executions, it means another `/execute-plan` session is running against the same codebase. This can cause branch and merge conflicts. Either wait for the other execution to finish or cancel it.
