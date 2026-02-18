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
- **Docker** (optional) if running PySpark locally
- **Databricks CLI** (optional) if executing on a Databricks cluster

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/init` | Scaffold a new project |
| `/next` | Advance to the next workflow step |
| `/status` | Show where you are and what to do |
| `/board` | Open the Kanban dashboard in your browser |
| `/prune-knowledge` | Clean up old solution docs |

You can always type `/status` to see your current phase and suggested next action, or `/next` to let the harness figure out what comes next.

---

## Step 1: Create Your Project

Start in an empty directory (or an existing repo where you want to add the harness).

```
/init
```

The harness will ask for your project name, then create the full project structure:

- `CLAUDE.md` — the project guide that Claude reads on every session (lives at the project root)
- `kyros-agent-workflow/project-state.yaml` — tracks your workflow progress
- `kyros-agent-workflow/.harnessrc` — project-specific configuration (edit this later for Databricks, team knowledge, etc.)
- `kyros-agent-workflow/docs/standards/` — coding standards, definition of done, review criteria
- `kyros-agent-workflow/docs/solutions/` — where learnings accumulate as you work

> **Note:** All project files live inside the `kyros-agent-workflow/` directory, with `CLAUDE.md` being the only file at the project root.

After init completes, run `/next` to begin.

---

## Step 2: Profile Your Data (Phase 1)

```
/next
```

The harness will:

1. **Ask where your data lives** — provide the path to your CSV, Parquet, or Excel file
2. **Profile the data automatically** — generates a detailed report covering column types, null rates, distributions, correlations, and quality issues
3. **Conduct an analyst Q&A** — you'll answer questions one at a time about the business objective, target variable, known data issues, columns to exclude, and domain constraints
4. **Ask for your sign-off** — confirm the data profile looks complete

**What you'll decide:** Answer the Q&A questions based on your domain knowledge. If the profile needs more exploration, say so.

**What gets created:**
- `kyros-agent-workflow/docs/context/data-profile.md` — structured data exploration
- `kyros-agent-workflow/docs/context/analyst-notes.md` — your Q&A responses

---

## Step 3: Define Your Epics (Phase 2)

```
/next
```

The harness will:

1. **Propose an epic breakdown** — a sequence of work chunks (e.g., Data Loading, Data Translation, Model Execution, Report Generation)
2. **Refine with you** — ask whether epics should be split, combined, reordered, or if any are missing
3. **Write epic specs** — each epic gets acceptance criteria and dependency info

**What you'll decide:** Shape the epic breakdown to match how you think about the project. This is the most important planning step — get it right here and everything downstream flows smoothly.

**What gets created:**
- `kyros-agent-workflow/docs/epics/01-name.yaml`, `02-name.yaml`, etc. — one spec per epic

---

## Step 4: Plan the Current Epic (Phase 3)

```
/next
```

For each epic, the harness will:

1. **Search for prior solutions** — a learnings-researcher agent checks your knowledge base (and team knowledge, if configured) for relevant patterns from past projects
2. **Break the epic into testable steps** — each step is one focused unit of work with clear acceptance criteria
3. **Write tests first (TDD)** — tests are written before any implementation code. They will all fail at this point — that's intentional.
4. **Create an implementation plan** — step-by-step instructions for what to build

**What you'll decide:** Approve the step breakdown and the implementation plan.

**Important:** The tests written here are locked. They cannot be modified during the build phase. This ensures the agent builds code that meets the original spec, not code that passes weakened tests.

---

## Step 5: Build (Phase 4)

```
/next
```

This is where the agent team does the heavy lifting. The harness forms a two-agent team:

- A **developer** who writes the implementation code
- A **reviewer** who checks each step against the acceptance criteria

For each step, the developer:
1. Reads the implementation plan
2. Writes code to pass the tests
3. Runs the test suite
4. Commits the work

Then the reviewer:
1. Checks the code against review criteria
2. Verifies tests pass and haven't been tampered with
3. Approves or requests changes

This loop continues until all steps in the epic are complete and approved.

**What you'll decide:** Usually nothing — this phase runs autonomously. You'll only be pulled in if the harness hits a circuit breaker (e.g., the same error 5 times, or review cycles exceeding 5 rounds).

**What happens in the background:**
- Solution docs are written automatically when the developer resolves tricky problems. These accumulate as your project's knowledge base.

---

## Step 6: Submit (Phase 5)

```
/next
```

The harness will:

1. **Run the Definition of Done** — automated checks for coverage, standards, documentation
2. **Run a quality scan** — flags any remaining issues
3. **Promote learnings** — if you have a shared team knowledge repo configured, universal solutions are offered for promotion
4. **Create a Pull Request** — with a summary of work, test results, and quality findings

**What you'll decide:** Review the PR and merge it when you're satisfied.

---

## Step 7: Repeat for Each Epic

After merging, run `/next` again. The harness advances to the next epic and returns to Phase 3 (Plan). The cycle repeats:

```
Plan → Build → Submit → (merge) → Plan → Build → Submit → ...
```

When the final epic is submitted and merged, the project is complete.

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

For fully hands-off execution, the harness can run on an isolated VM with `--dangerously-skip-permissions` mode. See `docs/infrastructure/vm-setup.md` for setup instructions.

**Never run in this mode on your local machine.**

When configured for VM execution, add to `kyros-agent-workflow/.harnessrc`:

```yaml
execution:
  mode: autonomous
  skip_permissions: true
  vm_id: "your-vm-id"
  idle_timeout_minutes: 60
```

The session-start hook will warn you if `skip_permissions` is enabled without a `vm_id` set.

---

## Troubleshooting

**"No project-state.yaml found"**
You're not in a harness project directory. Navigate to the correct project root (where `kyros-agent-workflow/project-state.yaml` exists) or run `/init` to start a new project.

**Circuit breaker triggered**
The harness stops when it detects the agent is stuck (same error 5+ times, no progress for 3+ iterations, or 5+ review rounds). Read the error context, decide whether to adjust the approach, and resume.

**Tests failing after plan phase**
That's expected. Phase 3 writes tests that intentionally fail — they define what the code should do before it exists. Phase 4 (build) makes them pass.

**Reviewer keeps requesting changes**
Check the review feedback. Common causes: missing acceptance criteria, coding standard violations, or regressions in other tests. The harness escalates to you after 5 review rounds.

**Dashboard not loading**
Make sure you're running `/board` from within a project directory that has `kyros-agent-workflow/project-state.yaml`. The dashboard reads that file to render the board.
