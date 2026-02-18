---
name: review-step
description: Use to manually invoke the reviewer agent on the current step's work, outside of the agent team flow.
---

# Review Step

## Overview

Manually invoke the reviewer agent to review the current step's work. This is useful when running outside the agent team flow or when the automatic review needs to be re-run.

## Process

1. Read `kyros-agent-workflow/project-state.yaml` to identify the current epic and step
2. Get the git diff since the last approved step (or TDD baseline)
3. Dispatch the **reviewer** subagent with the Task tool:
   - Provide: the step spec, the diff, test results, review criteria
4. Process the reviewer's output:
   - If approved: update state (`review_approved: true`), log progress
   - If changes requested: present feedback to the user/developer
