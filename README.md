# One-Shot Project Build

An agentic harness for Claude Code that enables fully autonomous execution of client predictive modeling and analysis projects.

## Vision

We build predictive models for our clients and then perform analysis on those models. Today, this work requires significant manual engineering effort. The goal of this project is to build a **generic harness** — not tied to any single client engagement — that enables Claude Code to agentically execute an entire project end-to-end: from data ingestion and exploration, through model building and validation, to final analysis and deliverables.

**Humans steer. Agents execute.**

## What This Is

This is not a specific model or pipeline. It is the **scaffolding, tooling, documentation structure, and feedback loops** that allow an AI coding agent (Claude Code) to:

- Understand the full scope of a client project from structured specifications
- Break the project into executable steps
- Write and execute code for data processing, modeling, and analysis
- Validate its own outputs against acceptance criteria
- Self-correct when things break
- Produce final deliverables ready for client review

## Inspiration & References

This project draws heavily from emerging best practices in "harness engineering" — the discipline of building environments that maximize agent effectiveness:

- [OpenAI: Harness Engineering — Leveraging Codex in an Agent-First World](https://openai.com/index/harness-engineering/) — Core reference on building agent-first development environments. Key lessons: repository knowledge as system of record, progressive disclosure via AGENTS.md, enforcing architecture mechanically, and increasing application legibility for agents.
- [Ryan Carson on agent-first workflows](https://x.com/ryancarson/status/2023452909883609111)
- [Rohit on agentic development patterns](https://x.com/rohit4verse/status/2021622526112358663)
- [Ryan Carson on scaffolding for agents](https://x.com/ryancarson/status/2020931274219594107)
- [Khaliq Gant on harness patterns](https://x.com/Khaliqgant/status/2019124627860050109)

## Key Principles (Adapted from Harness Engineering)

1. **Repository as system of record** — All project knowledge (specs, architecture, plans, constraints) lives in the repo, versioned and discoverable by the agent. If the agent can't see it, it doesn't exist.
2. **Progressive disclosure** — Give the agent a map, not a 1,000-page manual. A concise entry point (`CLAUDE.md`) with pointers to deeper sources of truth.
3. **Mechanical enforcement** — Enforce architectural constraints, coding standards, and quality gates via linters, tests, and validation scripts — not just documentation.
4. **Agent legibility** — Optimize everything for the agent's ability to reason about it: structured specs, clear directory layouts, typed interfaces, explicit acceptance criteria.
5. **Feedback loops** — The agent should be able to validate its own work, detect failures, and self-correct without human intervention for routine issues.
6. **Humans at the right layer** — Humans define goals, review outputs, and handle judgment calls. The agent handles execution.

## Installation

```bash
# Install as a Claude Code plugin
claude plugins install <path-to-this-repo>
```

### Prerequisites
- Claude Code (latest)
- Node.js 18+ (for BATS test runner)
- yq 4.x (for YAML processing)
- Python 3.10+ (for client projects)

## Quick Start

```bash
# 1. Scaffold a new project
/init

# 2. Check status at any time
/status

# 3. Advance to the next phase
/next
```

## Workflow Commands

| Command | Phase | Description |
|---------|-------|-------------|
| `/init` | Setup | Scaffold a new project from templates |
| `/status` | Any | Show current workflow state and next action |
| `/next` | Any | Auto-advance to the next workflow phase |
| `/gather-context` | Phase 1 | Profile data and conduct analyst Q&A |
| `/define-epics` | Phase 2 | Collaboratively break project into epics |
| `/plan-epic` | Phase 3 | Create TDD plan, write tests first |
| `/build` | Phase 4 | Agent team build/review loop |
| `/submit` | Phase 5 | Run DoD checks, create PR, advance |
| `/quality-scan` | Any | Run background quality checks |
| `/board` | Any | Launch Kanban dashboard |
| `/prune-knowledge` | Any | Clean up solution docs |

## Plugin Architecture

```
├── .claude-plugin/          # Plugin manifest
├── agents/                  # Agent definitions (reviewer, profiler, learnings-researcher)
├── commands/                # Slash commands (/init, /status, /next, etc.)
├── dashboard/               # Kanban board (HTML/CSS/JS + serve.sh)
├── hooks/                   # Session-start hook, enforcement scripts, self-check
├── lib/                     # State library (YAML read/write)
├── mcp/                     # MCP servers (Databricks executor)
├── skills/                  # Phase skills + utility skills
├── templates/               # Project scaffolding templates
├── tests/                   # BATS test suite (24 tests)
└── docs/                    # Architecture, plans, infrastructure guides
```

### Key Components

| Component | Description |
|-----------|-------------|
| **State library** | Read/write `project-state.yaml` with BATS tests |
| **Phase skills** | gather-context, define-epics, plan-epic, build-step, submit-epic |
| **Enforcement scripts** | Test immutability, definition-of-done, solution doc validation |
| **Self-check CLI** | Pre-completion verification (tests, immutability, docs, git status) |
| **Compound learning** | Solution docs with YAML schema, contradiction detection, cross-project promotion |
| **Learnings researcher** | Agent that searches prior solutions for relevant patterns |
| **Knowledge pruning** | Periodic cleanup of stale/superseded/duplicate solution docs |
| **Databricks MCP server** | Execute code, manage clusters, upload/download files via MCP |
| **Kanban dashboard** | Browser-based board with filtering, auto-refresh, dark mode |
| **VM isolation** | Setup guide and session-start safety warning for autonomous execution |

## Design Documentation

- Architecture: `docs/plans/2026-02-16-harness-architecture-design.md`
- Implementation plan: `docs/plans/2026-02-16-harness-implementation-plan.md`
- VM setup: `docs/infrastructure/vm-setup.md`

## Project Status

**Phase: Complete** — All 19 implementation epics built and reviewed. 24 BATS tests passing. Ready for integration testing on a real client project.
