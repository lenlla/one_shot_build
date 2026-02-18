---
name: run-on-databricks
description: Use when you need to execute PySpark code on Databricks for full-scale data processing, or when local Docker execution is insufficient (large datasets, production validation, Unity Catalog access).
---

# Run on Databricks

## Overview

Execute PySpark code on a Databricks cluster for scaled data processing. Use this when local Docker is insufficient.

## When to Use Databricks vs Local Docker

| Scenario | Use |
|----------|-----|
| Data profiling on samples (<100MB) | Local Docker |
| Unit tests with test fixtures | Local Docker |
| Development iteration (write-test-fix loop) | Local Docker |
| Full-scale data processing (>1GB) | **Databricks** |
| Integration tests against real data | **Databricks** |
| Production validation before PR | **Databricks** |
| Accessing Unity Catalog tables | **Databricks** |
| Performance benchmarking | **Databricks** |

## Process

### 1. Check cluster status
Use the `cluster_status` MCP tool. If terminated, use `start_cluster`.

### 2. Execute code
Use the `execute_code` MCP tool with your PySpark code.

Important:
- Set catalog and schema at the start: `spark.sql("USE CATALOG main; USE SCHEMA client_xyz")`
- Use the same code that runs locally — no Databricks-specific rewrites
- If the code requires files, upload them first with `upload_file`

### 3. Validate results
Compare Databricks output against local test expectations.
If results differ between local and Databricks, this is a bug — investigate.

### 4. Download artifacts
Use `download_file` to pull any generated artifacts back to the project repo.

## Configuration

Databricks settings are in `kyros-agent-workflow/.harnessrc` under the `databricks:` key.
The token is read from the environment variable specified in `token_env_var`.

## Important

- NEVER hardcode tokens or credentials in code or config files
- Always develop and test locally FIRST, then validate on Databricks
- Databricks execution is slower and costs money — use it intentionally
- If a cluster start fails, check with the human before retrying
