# Developer Agent Knowledge Access

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give the developer sub-agent access to project and team knowledge (solution docs) so it can reference prior solutions when implementing code, not just when planning.

**Architecture:** Update the build-step coordinator to read `.harnessrc` for `shared_knowledge_path`, then include solution doc paths in the developer prompt's Context Files section. Add a "search for relevant solutions before starting" instruction to the developer's Rules. Update the user guide to document this knowledge flow.

**Tech Stack:** Markdown (skills, docs)

---

### Task 1: Update the developer prompt in build-step skill

**Files:**
- Modify: `skills/build-step/SKILL.md:60-91` (developer sub-agent prompt)

**Step 1: Read the current file**

Read `skills/build-step/SKILL.md` to confirm the current developer prompt content.

**Step 2: Update the Context Files section**

In the developer sub-agent prompt (the code block starting at line 61), replace the `## Context Files` section:

```
## Context Files (read these first)

- Coding standards: kyros-agent-workflow/docs/standards/coding-standards.md
- Epic spec: <epic_spec_path>
- TDD baseline tag: <tdd_baseline_tag>
```

With:

```
## Context Files (read these first)

- Coding standards: kyros-agent-workflow/docs/standards/coding-standards.md
- Epic spec: <epic_spec_path>
- TDD baseline tag: <tdd_baseline_tag>
- Project solutions: kyros-agent-workflow/docs/solutions/
- Team solutions: <shared_knowledge_path>/docs/solutions/ (if configured in .harnessrc)
```

**Step 3: Add knowledge search instruction to Rules**

In the same developer prompt, add to the `## Rules` section, after the existing rules and before `## When Done`:

```
- Before starting implementation, search the project and team solution docs for patterns
  relevant to this step's component and problem domain. Look for docs matching the
  component type, data characteristics, or error patterns you expect to encounter.
  Apply any relevant patterns proactively — don't wait until you're stuck.
```

**Step 4: Verify the file reads correctly**

Read back `skills/build-step/SKILL.md` and confirm the developer prompt is well-formed.

**Step 5: Commit**

```bash
git add skills/build-step/SKILL.md
git commit -m "feat: add knowledge access to developer sub-agent prompt"
```

---

### Task 2: Update the fix-round developer prompt

**Files:**
- Modify: `skills/build-step/SKILL.md:153-166` (fix-round developer prompt)

The fix-round developer (dispatched when the reviewer requests changes) should also have access to solution docs — a prior solution might explain how to fix the reviewer's feedback.

**Step 1: Read the current fix-round prompt**

Read `skills/build-step/SKILL.md` lines 150-170 to see the current fix-round developer prompt.

**Step 2: Add knowledge reference to fix-round prompt**

In the fix-round developer prompt code block, add after `## Rules`:

```
- If the reviewer's feedback relates to a known pattern (data quality, type handling,
  performance, etc.), check kyros-agent-workflow/docs/solutions/ for existing solutions
  before implementing your fix.
```

**Step 3: Commit**

```bash
git add skills/build-step/SKILL.md
git commit -m "feat: add knowledge access to fix-round developer prompt"
```

---

### Task 3: Update the coordinator to read shared_knowledge_path

**Files:**
- Modify: `skills/build-step/SKILL.md:23-35` (Step 1: Read plan and initialize)

The coordinator already reads `.harnessrc` for circuit breaker thresholds and test commands. It should also extract `shared_knowledge_path` so it can pass it to developer prompts.

**Step 1: Read the current Step 1 section**

Read `skills/build-step/SKILL.md` lines 23-35.

**Step 2: Add shared_knowledge_path extraction**

After the existing line "Read `kyros-agent-workflow/.harnessrc` for project-specific configuration overrides (circuit breaker thresholds, model selection, test commands)." add:

```markdown
Extract `shared_knowledge_path` from `.harnessrc` if configured. This path will be passed to developer sub-agents so they can search team-level solution docs.
```

**Step 3: Commit**

```bash
git add skills/build-step/SKILL.md
git commit -m "feat: extract shared_knowledge_path in build-step coordinator"
```

---

### Task 4: Update user guide — Phase B knowledge flow

**Files:**
- Modify: `docs/user-guide.md:214-216` (Phase B "What happens in the background" section)

**Step 1: Read the current section**

Read `docs/user-guide.md` lines 210-220 to see the current "What happens in the background" section.

**Step 2: Add knowledge access bullet**

In the "What happens in the background" bullet list, add a new bullet before the existing two:

```markdown
- Each developer agent searches project and team solution docs for relevant patterns before starting implementation. This means knowledge captured during earlier epics (or from other projects via the shared knowledge repo) is available to developers working on later steps — even though each developer agent starts with a fresh context.
```

**Step 3: Commit**

```bash
git add docs/user-guide.md
git commit -m "docs: document developer knowledge access in user guide Phase B"
```

---

### Task 5: Final verification

**Step 1: Run all BATS tests**

Run: `npx bats tests/`
Expected: All tests pass (no tests are affected by doc-only changes, but verify nothing broke).

**Step 2: Verify cross-references**

Check that:
- `build-step/SKILL.md` developer prompt references `kyros-agent-workflow/docs/solutions/` (the path that `validate-solution-doc.sh` checks)
- `build-step/SKILL.md` developer prompt references `<shared_knowledge_path>/docs/solutions/` (matching `.harnessrc` config key)
- User guide Phase B mentions developer knowledge access
- The fix-round developer prompt also has knowledge access

**Step 3: Create PR**

```bash
git push -u origin feat/developer-knowledge-access
```

Create PR with title: "Give developer sub-agents access to project and team knowledge"
