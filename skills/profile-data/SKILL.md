---
name: profile-data
description: Profile client data tables. Creates one data-profile-<table>.md per table. Supports multiple tables. Detects existing profiles and asks whether to overwrite or create a new version.
---

# Profile Data

## Overview

Run automated data profiling on one or more client data tables. Each table gets its own profile report.

## Pre-Conditions

- Project has been initialized with `/init`
- Client data tables are accessible

## Process

### Step 1: Determine which tables to profile

Check if the user provided table paths as arguments to the `/profile-data` command.

If table paths were provided, use those directly.

If no arguments were provided, ask the user:
```
Which data tables should I profile? Please provide the full paths (e.g., catalog.schema.table_name).
```

### Step 2: Check for existing profiles

For each table, check if a `data-profile-<table>.md` already exists in `kyros-agent-workflow/docs/context/`.

If an existing profile is found, ask the user:
```
A profile for <table> already exists (created <date>). Would you like to:
1. Overwrite it
2. Create a new version (data-profile-<table>-v2.md)
3. Skip this table
```

### Step 3: Profile each table

For each table (sequentially), dispatch a **profiler sub-agent** with the Task tool:

**Prompt:**
```
You are profiling the data table: <table_path>

Read the profiler agent definition at agents/profiler.md and follow it exactly.

Write your output to: kyros-agent-workflow/docs/context/data-profile-<table_name>.md

When done, report back with:
- TABLE: <table_path>
- OUTPUT: <output file path>
- ROW_COUNT: <number of rows>
- COLUMN_COUNT: <number of columns>
```

Wait for each profiler to complete before starting the next.

### Step 4: Summary

After all tables are profiled, display a summary:
```
Profiling complete:
- <table_1>: <row_count> rows, <col_count> columns -> <output_file>
- <table_2>: <row_count> rows, <col_count> columns -> <output_file>

Next step: Run /define-epics to break the project into epics.
```
