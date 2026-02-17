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

## Project Status

**Phase: Planning** — Currently building the Product Requirements Document (PRD) for the harness.
