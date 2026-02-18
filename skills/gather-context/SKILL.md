---
name: gather-context
description: Profile client data tables. Creates one data-profile-<table>.md per table. Supports multiple tables. Detects existing profiles and asks whether to overwrite or create a new version.
---

# Profile Data

## Overview

Run automated data profiling on one or more client data tables. Each table gets its own profile report.

## Pre-Conditions

- Project has been initialized with `/init`
- Client data tables are accessible

## Process

### Step 1: Determine tables to profile

Check if the user provided table paths as arguments to the `/profile-data` command.

- **If arguments provided:** Use those as the table paths.
- **If no arguments:** Use AskUserQuestion to ask: "What tables should I profile? Provide the path(s) to your data tables (CSV, Excel, Parquet, or database table references). You can specify multiple tables separated by spaces."

### Step 2: Check for existing profiles

For each table, check if a profile already exists at `kyros-agent-workflow/docs/context/data-profile-<table-name>.md`.

If a profile exists for any table, use AskUserQuestion to ask for each one:
"A profile already exists for `<table-name>`. Would you like to:"
- Overwrite the existing profile
- Create a new version (saves as `data-profile-<table-name>-v<N>.md`)

### Step 3: Profile each table

For each table, dispatch the **profiler** subagent with the Task tool:
- subagent_type: use the `profiler` agent definition
- Prompt: "Profile the data at [path]. Write results to kyros-agent-workflow/docs/context/data-profile-<table-name>.md."
  - Include column types, distributions, null counts, unique values, min/max, data quality issues
  - If this is a versioned profile, use the versioned filename
- Wait for the profiler to complete before starting the next table

### Step 4: Present summaries

For each profiled table, read the generated profile and present a brief summary to the analyst:
- Number of rows and columns
- Key data quality concerns (high nulls, low variance, type mismatches)
- Notable patterns

### Step 5: Commit

```bash
git add kyros-agent-workflow/docs/context/data-profile-*.md
git commit -m "docs: add data profiles for <table-names>"
```

Tell the user: "Data profiling complete. You can now run `/define-epics` to plan your project, passing these profiles as context if desired."
