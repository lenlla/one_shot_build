# PRD: Client Project Harness

## Overview

A harness that enables an AI agent to execute client analytics projects end-to-end. The agent receives all human decisions upfront, then mechanically transforms data, runs models, and produces reports without making judgment calls.

## Problem

Client analytics projects follow a repeatable pattern — data translation, model fitting, report generation — but currently require significant manual execution time. The judgment-intensive parts (data mapping decisions, variable grouping, predictor selection, business-driven hyperparameters) are a small fraction of the work. The rest is mechanical execution that an agent can handle.

## Core Concept

**Humans decide, the agent executes.**

All design decisions are made by humans before the agent starts. These decisions are encoded in a project configuration that the agent consumes. The agent then runs the pipeline without making further judgment calls.

## What the Agent Does

### 1. Data Translation
Translate the client's data format into our standardized pipeline format.

- Column renaming and type casting based on an explicit mapping
- Variable level grouping (e.g., collapsing categorical levels) based on human-specified rules
- Dropping unmapped columns
- No inference or guessing — if a column isn't in the mapping, it's flagged

### 2. Model Execution
Run statistical/ML models with the provided configuration.

- **Model choice is not a judgment call** — it's specified in the config
- **Hyperparameters are provided** — defaults are generally good enough, but business-driven overrides are specified by humans
- The agent fits the model, extracts coefficients/predictions/summary stats
- No model selection, no hyperparameter tuning, no evaluation beyond what's mechanical

### 3. Report Generation
Produce structured output artifacts from the model results.

- Coefficient tables, prediction outputs, model summaries
- Formatted as CSV/JSON per the config
- **The agent produces the reporting; it does not analyze the results**
- Interpretation is left to humans

## What the Agent Does NOT Do

- Make data mapping decisions
- Choose which variables to group or how
- Select predictors
- Tune hyperparameters beyond provided defaults
- Interpret or analyze model outputs
- Make any business judgment calls

## Human-Provided Inputs (Project Config)

All decisions are surfaced by humans and provided to the agent at project start:

| Input | Description | Example |
|-------|-------------|---------|
| Column mappings | Client column name → standard name, with dtypes | `"cust_id" → "customer_id" (int)` |
| Variable groupings | How levels of a variable are combined | `region: {"north": ["ME","VT","NH"], "south": ["FL","GA"]}` |
| Predictor variables | Which variables enter the model | `["age", "income", "region"]` |
| Target variable | What the model predicts | `"churn"` |
| Model type | Which model to run | `"logistic_regression"` |
| Hyperparameters | Business-driven overrides to defaults | `{"max_iter": 2000, "C": 0.5}` |
| Report format | Output file formats and which artifacts to include | `formats: ["csv"], include_coefficients: true` |

## Operating Modes

### Autonomous Mode
For fully agentic end-to-end execution.

- Issues (data quality problems, missing columns, failed models) are **logged**
- Execution **continues** past non-fatal problems
- A complete issue log is written as a report artifact
- Humans review the log after the run completes

### Interactive Mode
For runs where human feedback is needed during execution.

- On warnings or errors, execution **pauses**
- The issue is surfaced to the human with context
- The human provides an instruction (e.g., "skip that column", "use this default")
- Execution resumes with the feedback incorporated

## Pipeline Stages

```
[Project Config (YAML)] + [Client Data File]
        │
        ▼
   ┌─────────┐
   │  Load    │  Read client data (CSV/Excel/JSON/Parquet)
   └────┬────┘
        │
        ▼
   ┌──────────┐
   │ Translate │  Column mappings, type casts, variable groupings
   └────┬─────┘
        │
        ▼
   ┌─────────┐
   │  Model   │  Fit models with provided config & hyperparameters
   └────┬────┘
        │
        ▼
   ┌──────────┐
   │  Report  │  Write coefficients, predictions, summaries, issue log
   └──────────┘
```

## Issue Handling by Severity

| Severity | Autonomous Mode | Interactive Mode | Examples |
|----------|----------------|-----------------|----------|
| Info | Log | Log | "Loaded 5000 rows", "Dropping 3 unmapped columns" |
| Warning | Log, continue | Pause, ask | Missing column in mapping, type cast failure, unmapped variable levels |
| Error | Log, continue (with degraded output) | Pause, ask | Model training failure, input file unreadable |

## Success Criteria

- Given a valid config and client data file, the agent produces all specified report artifacts without human intervention (autonomous mode)
- All issues encountered during execution are captured in the issue log
- The pipeline is deterministic — same config + same data = same output
- No judgment calls are embedded in the agent's execution path

## Open Questions

1. **Config validation** — Should the agent validate the config against the data before starting execution, or discover issues as it goes?
2. **Partial output** — If a model fails, should the report still include outputs from models that succeeded?
3. **Data quality thresholds** — Should there be config-driven thresholds (e.g., "fail if >20% of rows have nulls in target column") or is that a human decision made post-hoc from the issue log?
