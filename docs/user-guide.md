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

1. **Ask for your starting point** — do you already have epics in mind, or would you like it to search the knowledge base for similar past projects as inspiration?
2. **Propose an epic breakdown** — based on your input (or learnings from past projects), propose a sequence of work chunks (e.g., Data Loading, Data Translation, Model Execution, Report Generation)
3. **Refine with you** — ask whether epics should be split, combined, reordered, or if any are missing
4. **Write epic specs** — each epic gets acceptance criteria and dependency info

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

This is where the agent team does the heavy lifting. The harness uses Claude Code's **agent team** feature to create a three-role team, where each agent runs in its own context window:

- **Team lead** (you/Claude) — coordinates the workflow, populates the task list with steps from the implementation plan, monitors for stuck loops, and updates `kyros-agent-workflow/project-state.yaml` after each approved step. The lead operates in delegate mode — it coordinates but does not write code.
- **Developer agent** — implements the code, one step at a time. Has its own context focused on the implementation plan, source code, and test output.
- **Reviewer agent** — reviews each completed step. Has its own context focused on the diff, coding standards, and acceptance criteria. The reviewer is adversarial — its job is to catch problems, not rubber-stamp approvals.

Because each agent has its own context, they can focus deeply on their role without being cluttered by the other's work.

### The developer/reviewer loop

For each step in the epic, the team runs a build/review loop:

```
Developer                          Reviewer
    │                                  │
    ├─ Read implementation plan        │
    ├─ Write code to pass tests        │
    ├─ Run test suite                  │
    ├─ Self-review & commit            │
    ├─────── hand off ────────────────>│
    │                                  ├─ Read the git diff
    │                                  ├─ Check against review criteria
    │                                  ├─ Verify tests pass independently
    │                                  ├─ Check test immutability
    │                                  │
    │                          ┌───────┤
    │                          │ Pass? │
    │                          └───┬───┘
    │                    No ───┐   │
    │                          │   └─── Yes: Approve step
    │<── specific feedback ────┘              │
    ├─ Fix issues                             │
    ├─ Re-commit                        Lead updates state
    ├─────── hand off ────────────────>│
    │                                  ├─ Re-review the fixes
    │                                  └─ ...
```

When the reviewer requests changes, the feedback is specific: which criterion failed, what file and line is wrong, and what needs to change. The developer then fixes only what was flagged and hands off again. This loop repeats until the reviewer approves — or until it exceeds 5 rounds, at which point the lead halts and escalates to you.

### What the lead monitors

The team lead watches for circuit breaker signals:

| Signal | Threshold | What happens |
|--------|-----------|--------------|
| No file changes | 3 iterations | Lead warns developer, suggests different approach |
| Same error repeated | 5 times | Lead halts the team and escalates to you |
| Review rounds exceeded | 5 rounds | Lead halts the team and escalates to you |

**What you'll decide:** Usually nothing — this phase runs autonomously. You'll only be pulled in if the lead hits a circuit breaker.

**What happens in the background:**
- Solution docs are written automatically when the developer resolves tricky problems. These accumulate in `kyros-agent-workflow/docs/solutions/` as your project's knowledge base.
- The reviewer validates that any new solution docs have correct YAML frontmatter.

### At the end of each epic

When all steps in the epic are built and approved:

1. The lead asks the developer: "Is this project-specific or team-wide?" for each solution doc created during the epic. Project-specific docs stay in `kyros-agent-workflow/docs/solutions/`; team-wide docs are flagged for promotion to the shared knowledge repo (which happens in the next phase).
2. The lead updates `kyros-agent-workflow/project-state.yaml` to mark the phase as `submit`.
3. The **developer and reviewer agents are cleaned up** — their contexts are discarded. The lead (your main Claude Code session) continues and tells you to run `/submit`.

The cross-epic loop is driven by you: after submitting a PR, you run `/next` again, which advances to the next epic's planning phase and eventually creates a fresh developer/reviewer team for that epic. Each epic gets a clean agent team, but the workflow state in `kyros-agent-workflow/project-state.yaml` carries continuity across epics.

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
