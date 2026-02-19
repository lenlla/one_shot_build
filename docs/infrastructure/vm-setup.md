# Isolated VM Setup Guide

## Overview

The one-shot-build harness is designed to run on an isolated VM with
`--dangerously-skip-permissions` mode for fully autonomous operation.
**Never run in this mode on a developer's local machine.**

## Prerequisites

| Component | Version | Purpose |
|-----------|---------|---------|
| Ubuntu | 22.04+ | Base OS |
| Docker | 24+ | Local PySpark container |
| Claude Code | Latest | Agent runtime |
| Python | 3.10+ | Project dependencies |
| Git | 2.40+ | Version control |
| Databricks CLI | Latest | Cluster access |
| yq | 4.x | YAML processing |
| Node.js | 18+ | BATS test runner |

## Setup Steps

### 1. Install Claude Code
```bash
# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code
```

### 2. Configure permissions mode
```bash
# Launch with skip permissions (VM ONLY)
claude --dangerously-skip-permissions
```

### 3. Install the plugin
```bash
claude plugins install <plugin-repo-url>
```

### 4. Configure credentials
Set environment variables (never store in files):
```bash
export ANTHROPIC_API_KEY="..."
export DATABRICKS_TOKEN="..."
export GITHUB_TOKEN="..."
```

### 5. Verify Docker
```bash
docker run --rm pyspark-dev:latest spark-submit --version
```

### 6. Verify Databricks connectivity
```bash
databricks clusters get --cluster-id <id>
```

## Security Considerations

- VM should have no access to production databases or systems
- Network egress should be limited to: Anthropic API, GitHub, Databricks workspace
- Credentials should be injected via secrets manager, not baked into the VM image
- VM should auto-terminate after configurable idle timeout
- All agent activity is logged to `<epics-dir>/claude-progress.txt` and git history for auditability
