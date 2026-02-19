---
name: define-epics
description: Brainstorm what to build, gather context, and collaboratively define project epics. Opens with "What do you want to build today?" If data profiles are provided as context, asks targeted data questions. Saves epic YAML specs to kyros-agent-workflow/builds/<name>/epic-specs/.
---

# Define Epics

## Overview

A collaborative brainstorming and planning session. Explore what the analyst wants to build, understand the context, then break the work into sequential epics.

## Process

### Step 1: Open the brainstorming

Start with: **"What do you want to build today?"**

Let the analyst describe their vision. Listen and ask follow-up questions ONE at a time. Prefer multiple-choice questions when possible.

### Step 2: Gather context

Check if the user provided context file paths as arguments to the `/define-epics` command.

- **If arguments provided:** Read each file. Acknowledge what you've learned from each.
- **If no arguments:** Use AskUserQuestion: "Can you point me to any relevant context? This could include data profiles, requirements docs, existing code, or configuration files. Provide file paths or say 'none' to continue."

Read all provided context files.

### Step 3: Data-specific questions (if data profile provided)

If any of the context files is a data profile (`data-profile-*.md`), ask targeted questions about the data. ONE question at a time:

- "I see [N] columns in [table]. Are there columns that should be excluded from analysis?"
- "The [column] has [X]% null values. Is this expected? How should nulls be handled?"
- "I notice [pattern]. Is this a known characteristic of this data?"
- "What is the target variable for modeling?"
- "Are there any domain-specific constraints I should know about?"

Only ask questions that are relevant based on what the profile reveals. Skip questions where the answer is obvious from the data.

### Step 4: Search knowledge base (optional)

If a shared knowledge repo is configured in `.harnessrc` (`shared_knowledge_path`), ask the analyst:
"Would you like me to search past projects for similar work that could inform our epic breakdown?"

If yes, dispatch the **learnings-researcher** subagent with project context. Use findings to inform the epic proposal.

### Step 5: Propose epic breakdown

Based on everything gathered, propose a breakdown of the project into sequential epics:

```
## Proposed Epics

1. **[Epic Name]** — [One-line description]
   - Acceptance criteria: [2-3 bullet points]
2. **[Epic Name]** — [One-line description]
   - Acceptance criteria: [2-3 bullet points]
...
```

Lead with your recommended breakdown and explain the reasoning.

### Step 6: Refine with analyst

Ask ONE question at a time to refine:
- "Does this epic breakdown match how you see the project?"
- "Should any epics be split or combined?"
- "What's the right order?"
- "Are there epics I'm missing?"

Iterate until the analyst approves the breakdown.

### Step 7: Name the build

Use AskUserQuestion: "What should I name this build? Examples: `v1`, `initial-model`, `feature-x`"

Create the build directory structure at `kyros-agent-workflow/builds/<name>/epic-specs/`.

### Step 8: Write epic specs

For each agreed epic, create a YAML file in the build's epic-specs directory:

```yaml
# kyros-agent-workflow/builds/<name>/epic-specs/01-<epic-name>.yaml
name: "[Epic Name]"
description: "[Detailed description]"
acceptance_criteria:
  - "[Criterion 1]"
  - "[Criterion 2]"
  - "[Criterion 3]"
dependencies: []
estimated_steps: 4
```

Number the files to preserve ordering (01-, 02-, etc.).

### Step 9: Commit

```bash
git add kyros-agent-workflow/builds/<name>/
git commit -m "docs: define epics in builds/<name>"
```

Tell the user: "Epics defined in `kyros-agent-workflow/builds/<name>/epic-specs/`. When you're ready to start building, run `/execute-plan kyros-agent-workflow/builds/<name>` or `/execute-plan-autonomously kyros-agent-workflow/builds/<name>`."
