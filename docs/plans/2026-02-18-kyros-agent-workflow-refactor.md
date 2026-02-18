# Plan: Move init-created files into `kyros-agent-workflow/` directory

## Context

When `/init` scaffolds a new client project, it currently creates files at the project root (`project-state.yaml`, `.harnessrc`, `docs/`, `src/`, `tests/`, etc.) alongside the repo's own files. The user wants all harness-created files contained in a single `kyros-agent-workflow/` subdirectory, with `CLAUDE.md` as the sole exception (it stays at root because Claude Code expects it there).

**Result:** A client project will look like:
```
client-repo/
├── CLAUDE.md                          # stays at root
└── kyros-agent-workflow/              # everything else
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

## Approach: Single constant `HARNESS_DIR`

Define `HARNESS_DIR="kyros-agent-workflow"` in `lib/state.sh`. All shell code derives paths from this. Skills and templates use the literal directory name in their instructions.

---

## Task 1: Update state library (`lib/state.sh`)

**Files:** `lib/state.sh`

Add `HARNESS_DIR` constant and update derived paths:

```bash
HARNESS_DIR="kyros-agent-workflow"
STATE_FILE="${PROJECT_ROOT}/${HARNESS_DIR}/project-state.yaml"
PROGRESS_FILE="${PROJECT_ROOT}/${HARNESS_DIR}/claude-progress.txt"
```

**Commit:** `refactor: add HARNESS_DIR constant to state library`

---

## Task 2: Update BATS tests for new paths

**Files:** `tests/state_test.bats`, `tests/session_start_test.bats`, `tests/check_test_immutability_test.bats`, `tests/definition_of_done_test.bats`, `tests/validate_solution_doc_test.bats`

Tests create temp directories with `project-state.yaml` at root. Update them to create files under `kyros-agent-workflow/` subdirectory instead.

For each test file:
- Read the current file
- Find where temp directories are set up (typically in `setup()` functions)
- Where `project-state.yaml` is created, create it under `kyros-agent-workflow/` subdirectory
- Where `claude-progress.txt` is referenced, update the path
- Where `.harnessrc` is referenced, update the path
- Where `tests/` directory is created for test fixtures, create under `kyros-agent-workflow/tests/`
- Where `src/` directory is created for test fixtures, create under `kyros-agent-workflow/src/`
- Where `docs/solutions/` is created, create under `kyros-agent-workflow/docs/solutions/`

Run `npx bats tests/*.bats` after changes to verify all 24 tests pass.

**Commit:** `test: update BATS test fixtures for kyros-agent-workflow directory`

**Depends on:** Task 1

---

## Task 3: Update hooks for new paths

**Files:**
- `hooks/session-start.sh`
- `hooks/self-check.sh`
- `hooks/check-test-immutability.sh`
- `hooks/definition-of-done.sh`
- `hooks/quality-scan.sh`

For `session-start.sh`:
- The script sources `lib/state.sh` which provides `$STATE_FILE` and `$HARNESS_DIR`
- Update line 71: `$PROJECT_ROOT/.harnessrc` → `$PROJECT_ROOT/$HARNESS_DIR/.harnessrc`
- Update line 72-73: both `yq eval` commands to use `$PROJECT_ROOT/$HARNESS_DIR/.harnessrc`

For `self-check.sh`:
- Read the current file first
- Update `pytest tests/` → `pytest kyros-agent-workflow/tests/`
- Update solution doc git diff path to use `kyros-agent-workflow/docs/solutions/`

For `check-test-immutability.sh`:
- Read the current file first
- Update `-- 'tests/'` → `-- 'kyros-agent-workflow/tests/'`

For `definition-of-done.sh`:
- Read the current file first
- Update any `src/` or `tests/` path references to use `kyros-agent-workflow/` prefix

For `quality-scan.sh`:
- Read the current file first
- Update any `src/` path references to use `kyros-agent-workflow/` prefix

Run `npx bats tests/*.bats` after changes to verify no regressions.

**Commit:** `refactor: update hooks for kyros-agent-workflow directory structure`

**Depends on:** Task 1

---

## Task 4: Update templates

**Files:**
- `templates/CLAUDE.md.template`
- `templates/.harnessrc.template`
- `templates/definition-of-done.md.template`

For `CLAUDE.md.template`:
- Update "Current State" section: `project-state.yaml` → `kyros-agent-workflow/project-state.yaml`
- Update `claude-progress.txt` → `kyros-agent-workflow/claude-progress.txt`
- Update Key Files table: prefix all paths with `kyros-agent-workflow/`
- Update Standards section: `docs/standards/` → `kyros-agent-workflow/docs/standards/`

For `.harnessrc.template`:
- Update testing commands:
  - `pytest tests/` → `pytest kyros-agent-workflow/tests/`
  - `ruff check src/ tests/` → `ruff check kyros-agent-workflow/src/ kyros-agent-workflow/tests/`
  - `ruff format src/ tests/` → `ruff format kyros-agent-workflow/src/ kyros-agent-workflow/tests/`

For `definition-of-done.md.template`:
- Read the file first
- Update any references to `project-state.yaml`, `claude-progress.txt`, `src/`, `tests/`

**Commit:** `refactor: update templates for kyros-agent-workflow directory structure`

---

## Task 5: Update init skill

**Files:** `skills/harness-init/SKILL.md`

- Update the directory structure diagram to show `kyros-agent-workflow/` as the root container
- Keep CLAUDE.md at project root in the diagram
- Update template mapping to show output paths under `kyros-agent-workflow/`:
  - `templates/project-state.yaml.template` → `kyros-agent-workflow/project-state.yaml`
  - `templates/.harnessrc.template` → `kyros-agent-workflow/.harnessrc`
  - `templates/definition-of-done.md.template` → `kyros-agent-workflow/docs/standards/definition-of-done.md`
  - etc.
- Update `claude-progress.txt` path in "After Scaffolding" section
- Update `docs/solutions/patterns/critical-patterns.md` → `kyros-agent-workflow/docs/solutions/patterns/critical-patterns.md`

**Commit:** `refactor: update init skill for kyros-agent-workflow directory structure`

---

## Task 6: Update phase skills (5 files)

**Files:**
- `skills/gather-context/SKILL.md`
- `skills/define-epics/SKILL.md`
- `skills/plan-epic/SKILL.md`
- `skills/build-step/SKILL.md`
- `skills/submit-epic/SKILL.md`

For each skill, read the current file and update all path references:

`gather-context`: `docs/context/` → `kyros-agent-workflow/docs/context/`
`define-epics`: `docs/epics/` → `kyros-agent-workflow/docs/epics/`, `project-state.yaml` → `kyros-agent-workflow/project-state.yaml`
`plan-epic`: `docs/plans/` → `kyros-agent-workflow/docs/plans/`, `tests/` → `kyros-agent-workflow/tests/`, `docs/epics/` → `kyros-agent-workflow/docs/epics/`
`build-step`: `src/` → `kyros-agent-workflow/src/`, `tests/` → `kyros-agent-workflow/tests/`, `docs/solutions/` → `kyros-agent-workflow/docs/solutions/`, `.harnessrc` → `kyros-agent-workflow/.harnessrc`, `docs/standards/` → `kyros-agent-workflow/docs/standards/`
`submit-epic`: `docs/solutions/` → `kyros-agent-workflow/docs/solutions/`, `project-state.yaml` → `kyros-agent-workflow/project-state.yaml`, `claude-progress.txt` → `kyros-agent-workflow/claude-progress.txt`

**Commit:** `refactor: update phase skills for kyros-agent-workflow directory structure`

---

## Task 7: Update utility skills (5 files)

**Files:**
- `skills/harness-status/SKILL.md`
- `skills/quality-scan/SKILL.md`
- `skills/prune-knowledge/SKILL.md`
- `skills/review-step/SKILL.md`
- `skills/run-on-databricks/SKILL.md`

For each skill, read the current file and update all path references:

`harness-status`: `project-state.yaml` → `kyros-agent-workflow/project-state.yaml`
`quality-scan`: `src/` → `kyros-agent-workflow/src/`, `tests/` → `kyros-agent-workflow/tests/`
`prune-knowledge`: `docs/solutions/` → `kyros-agent-workflow/docs/solutions/`, `.harnessrc` → `kyros-agent-workflow/.harnessrc`
`review-step`: `project-state.yaml` → `kyros-agent-workflow/project-state.yaml`
`run-on-databricks`: `.harnessrc` → `kyros-agent-workflow/.harnessrc`

**Commit:** `refactor: update utility skills for kyros-agent-workflow directory structure`

---

## Task 8: Update agents (3 files)

**Files:**
- `agents/reviewer.md`
- `agents/profiler.md`
- `agents/learnings-researcher.md`

For each agent, read the current file and update path references:

`reviewer.md`: `tests/` → `kyros-agent-workflow/tests/`, `src/` → `kyros-agent-workflow/src/`, `docs/standards/` → `kyros-agent-workflow/docs/standards/`
`profiler.md`: `docs/context/` → `kyros-agent-workflow/docs/context/`
`learnings-researcher.md`: `docs/solutions/` → `kyros-agent-workflow/docs/solutions/`, `.harnessrc` → `kyros-agent-workflow/.harnessrc`

**Commit:** `refactor: update agent definitions for kyros-agent-workflow directory structure`

---

## Task 9: Update dashboard and MCP server

**Files:**
- `dashboard/serve.sh`
- `dashboard/app.js`
- `mcp/databricks-executor/server.py`

For `serve.sh`:
- Update: `$PROJECT_ROOT/project-state.yaml` → `$PROJECT_ROOT/kyros-agent-workflow/project-state.yaml`

For `app.js`:
- Find the STATE_PATH or equivalent constant and update from `'/project-state.yaml'` to `'/kyros-agent-workflow/project-state.yaml'`

For `server.py`:
- Update: `Path.cwd() / ".harnessrc"` → `Path.cwd() / "kyros-agent-workflow" / ".harnessrc"`

**Commit:** `refactor: update dashboard and MCP server for kyros-agent-workflow directory structure`

---

## Task 10: Update documentation

**Files:**
- `docs/user-guide.md`

Update all path references throughout the user guide to use `kyros-agent-workflow/` prefix. Key sections:
- Step 1 (init): describe the new directory structure
- Configuration section: `.harnessrc` → `kyros-agent-workflow/.harnessrc`
- All references to `project-state.yaml`, `docs/solutions/`, etc.

**Commit:** `docs: update user guide for kyros-agent-workflow directory structure`

---

## Verification

After all tasks complete:

1. Run `npx bats tests/*.bats` — all 24 tests must pass
2. Grep for orphaned references:
   ```bash
   grep -rn "project-state\.yaml" --include="*.sh" --include="*.md" --include="*.py" --include="*.js" | grep -v kyros-agent-workflow | grep -v node_modules | grep -v "plans/2026-02-16"
   ```
   Should return nothing (except historical plan docs).
3. Same grep for `.harnessrc`, `claude-progress.txt`, checking they all have the `kyros-agent-workflow/` prefix where appropriate.

## Dependency graph

```
Task 1 (state.sh)
  ├── Task 2 (tests) — depends on Task 1
  ├── Task 3 (hooks) — depends on Task 1
  └── (everything else can run in parallel)

Task 4 (templates) — independent
Task 5 (init skill) — independent
Task 6 (phase skills) — independent
Task 7 (utility skills) — independent
Task 8 (agents) — independent
Task 9 (dashboard + MCP) — independent
Task 10 (docs) — independent
```

Tasks 4-10 are all independent of each other and can run in parallel.
Tasks 2-3 depend on Task 1 (state.sh must be updated first so tests can reference HARNESS_DIR).
