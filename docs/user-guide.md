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
| `/profile-data [paths]` | Profile data tables and conduct analyst Q&A |
| `/define-epics [context-files]` | Collaboratively break the project into epics |
| `/execute-plan <epics-dir>` | Execute epics interactively (plan, build, submit loop) |
| `/execute-plan-autonomously <epics-dir>` | Execute epics with minimal human intervention |
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

> **Note:** All project files live inside the `kyros-agent-workflow/` directory, with `CLAUDE.md` being the only file at the project root. Execution state is tracked per epics directory in `.execution-state.yaml`, created when you run `/execute-plan`.

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
4. **Ask you to name the epics directory** — you choose where specs are saved (e.g., `epics/v1`)
5. **Write epic specs** — each epic gets a YAML spec with acceptance criteria and dependency info

**What you'll decide:** Shape the epic breakdown to match how you think about the project. This is the most important planning step — get it right here and everything downstream flows smoothly.

**What gets created:**
- `<epics-dir>/01-name.yaml`, `02-name.yaml`, etc. — one spec per epic

---

## Step 4: Execute Your Epics

This is where the bulk of the work happens. The `/execute-plan` command orchestrates the full plan/build/submit cycle for every epic in your epics directory.

### Choose your execution mode

**Interactive mode** (recommended for first use):
```
/execute-plan <epics-dir>
```
Pauses at key checkpoints for your approval: after planning, after building, and after creating a PR. You stay in control.

**Autonomous mode** (for VM execution):
```
/execute-plan-autonomously <epics-dir>
```
Runs the full cycle end-to-end with minimal human intervention. Auto-merges PRs and advances to the next epic automatically. Best used on an isolated VM with `--dangerously-skip-permissions`.

### Startup checks

Before execution begins, the orchestrator will:

1. **Verify the epics directory** — confirms it exists and contains `.yaml` epic specs
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

The orchestrator dispatches a **build-step sub-agent** that uses Claude Code's **agent team** feature to create a three-role team, where each agent runs in its own context window:

- **Team lead** — coordinates the workflow, populates the task list with steps from the implementation plan, monitors for stuck loops, and updates state after each approved step. The lead operates in delegate mode — it coordinates but does not write code.
- **Developer agent** — implements the code, one step at a time. Has its own context focused on the implementation plan, source code, and test output.
- **Reviewer agent** — reviews each completed step. Has its own context focused on the diff, coding standards, and acceptance criteria. The reviewer is adversarial — its job is to catch problems, not rubber-stamp approvals.

Because each agent has its own context, they can focus deeply on their role without being cluttered by the other's work.

**The developer/reviewer loop:**

For each step in the epic, the team runs a build/review loop:

```
Developer                          Reviewer
    |                                  |
    +- Read implementation plan        |
    +- Write code to pass tests        |
    +- Run test suite                  |
    +- Self-review & commit            |
    +---------- hand off ------------->|
    |                                  +- Read the git diff
    |                                  +- Check against review criteria
    |                                  +- Verify tests pass independently
    |                                  +- Check test immutability
    |                                  |
    |                          +-------+
    |                          | Pass? |
    |                          +---+---+
    |                    No ---+   |
    |                          |   +--- Yes: Approve step
    |<-- specific feedback ----+              |
    +- Fix issues                             |
    +- Re-commit                        Lead updates state
    +---------- hand off ------------->|
    |                                  +- Re-review the fixes
    |                                  +- ...
```

When the reviewer requests changes, the feedback is specific: which criterion failed, what file and line is wrong, and what needs to change. The developer then fixes only what was flagged and hands off again. This loop repeats until the reviewer approves — or until it exceeds 5 rounds, at which point the lead halts and escalates to you.

**Circuit breaker monitoring:**

The team lead watches for stuck loops:

| Signal | Threshold | What happens |
|--------|-----------|--------------|
| No file changes | 3 iterations | Lead warns developer, suggests different approach |
| Same error repeated | 5 times | Lead halts the team and escalates to you |
| Review rounds exceeded | 5 rounds | Lead halts the team and escalates to you |

**What happens in the background:**
- Solution docs are written automatically when the developer resolves tricky problems. These accumulate in `kyros-agent-workflow/docs/solutions/` as your project's knowledge base.
- The reviewer validates that any new solution docs have correct YAML frontmatter.

#### Phase C: Submit

The orchestrator dispatches a **submit-epic sub-agent** that:

1. **Runs the Definition of Done** — automated checks that all tests pass, no TODO comments or debug prints remain, test immutability is verified, and `<epics-dir>/claude-progress.txt` is up to date
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
- **Autonomous mode:** Logs completion to `<epics-dir>/claude-progress.txt`

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

### Agent team configuration

Choose which models the developer and reviewer agents use:

```yaml
agent_team:
  developer_model: "sonnet"
  reviewer_model: "sonnet"
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
   /execute-plan-autonomously <epics-dir>
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
The harness stops when it detects the agent is stuck (same error 5+ times, no progress for 3+ iterations, or 5+ review rounds). Read the error context, decide whether to adjust the approach, and resume with `/execute-plan <epics-dir>` (it will offer to resume from where it left off).

**Tests failing after plan phase**
That's expected. The plan phase writes tests that intentionally fail — they define what the code should do before it exists. The build phase makes them pass.

**Reviewer keeps requesting changes**
Check the review feedback. Common causes: missing acceptance criteria, coding standard violations, or regressions in other tests. The harness escalates to you after 5 review rounds.

**Dashboard not loading**
Make sure you're running `/board` from within a project directory that has an active execution. The dashboard reads `.execution-state.yaml` to render the board.

**Concurrent execution warning**
If you see a warning about other active executions, it means another `/execute-plan` session is running against the same codebase. This can cause branch and merge conflicts. Either wait for the other execution to finish or cancel it.
