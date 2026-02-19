---
name: quality-scan
description: Use to run a background quality scan checking for coding standard deviations, unused imports, hand-rolled helpers, and other drift.
---

# Quality Scan

## Overview

Run a background quality check on the codebase. This can be invoked at any time to catch drift from coding standards.

## Process

1. Run the quality scan script: `bash <plugin_root>/hooks/quality-scan.sh`
2. Present findings to the user
3. If findings exist, offer to fix them:
   - Auto-fixable issues (unused imports, formatting) → fix and commit
   - Manual issues (TODOs, missing type hints) → list for the user to address
4. Log the scan to `<epics_dir>/claude-progress.txt` (if running within an execution context)

## When to Run

- After completing an epic (before /submit)
- Periodically during long build phases
- When the user explicitly requests `/quality-scan`
