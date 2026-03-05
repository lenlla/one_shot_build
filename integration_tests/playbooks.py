"""Deterministic multi-turn prompts used by strict integration tests."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TurnSpec:
    """One deterministic Claude turn in a playbook."""

    prompt_template: str
    max_turns: int
    required_signals: list[str] = field(default_factory=list)

    def render_prompt(self, **context: str) -> str:
        return self.prompt_template.format(**context)


@dataclass(frozen=True)
class Playbook:
    """Ordered set of turns and stop conditions for a test scenario."""

    name: str
    turns: list[TurnSpec]
    stop_conditions: list[str] = field(default_factory=list)


define_epics_playbook = Playbook(
    name="define-epics",
    turns=[
        TurnSpec(
            prompt_template=(
                "/define-epics {build_path}\n"
                "Draft epics from project context and stop for approval before persisting files."
            ),
            max_turns=4,
            required_signals=["Skill", "TodoWrite", "define-epics"],
        ),
        TurnSpec(
            prompt_template=(
                "Continue the previous define-epics session.\n"
                "Approval granted: persist epic YAML specs under {epic_specs_path} now.\n"
                "Write at least two files and confirm exact saved paths."
            ),
            max_turns=6,
            required_signals=["write", "epic", "saved"],
        ),
    ],
    stop_conditions=["epic specs persisted"],
)


resume_playbook = Playbook(
    name="resume",
    turns=[
        TurnSpec(
            prompt_template=(
                "/execute-plan {target}\n"
                "Initialize state and start execution in this turn."
            ),
            max_turns=4,
            required_signals=["execution state", "started"],
        ),
        TurnSpec(
            prompt_template=(
                "Continue the previous execute-plan run for {target}.\n"
                "Use the existing execution state and advance at least one epic status this turn.\n"
                "Report the specific state transition you made."
            ),
            max_turns=8,
            required_signals=["continue", "resum", "existing state"],
        ),
    ],
    stop_conditions=["state progressed after continuation"],
)


circuit_breaker_playbook = Playbook(
    name="circuit-breaker",
    turns=[
        TurnSpec(
            prompt_template=(
                "/one-shot-build:execute-plan-autonomously {target}\n"
                "Run in strict safeguard mode.\n"
                "If progress stalls, the same error repeats, or acceptance criteria are unsatisfiable,\n"
                "trigger the circuit breaker immediately and set the epic status to halted."
            ),
            max_turns=6,
            required_signals=["execute-plan", "circuit", "status"],
        ),
        TurnSpec(
            prompt_template=(
                "Continue the same autonomous execute-plan run and stop only after terminal breaker status is explicit.\n"
                "Do not continue implementation if breaker conditions are met.\n"
                "Set terminal halted status and report the exact breaker condition and resulting status."
            ),
            max_turns=8,
            required_signals=["continue", "terminal", "breaker"],
        ),
    ],
    stop_conditions=["terminal breaker status reached"],
)


profile_data_playbook = Playbook(
    name="profile-data",
    turns=[
        TurnSpec(
            prompt_template=(
                "/one-shot-build:profile-data {table_path}\n"
                "Complete profiling now. If prompted about existing profiles, choose overwrite.\n"
                "After profiling, ensure kyros-agent-workflow/docs/context/analyst-notes.md exists with target and key notes."
            ),
            max_turns=6,
            required_signals=["profile", "Task", "data-profile"],
        ),
        TurnSpec(
            prompt_template=(
                "Continue the previous profile-data run and finish all remaining actions.\n"
                "Ensure both data-profile output and analyst-notes.md are written."
            ),
            max_turns=6,
            required_signals=["continue", "profile", "analyst-notes"],
        ),
    ],
    stop_conditions=["profile artifacts written"],
)


execute_plan_playbook = Playbook(
    name="execute-plan",
    turns=[
        TurnSpec(
            prompt_template=(
                "/one-shot-build:execute-plan-autonomously {build_target}\n"
                "Run full plan->build->submit for all epics in this build.\n"
                "Do not stop for approvals; continue until epics complete or a terminal halt occurs.\n"
                "For each epic, ensure git branch epic/<epic-name> exists and tag tdd-baseline-<epic-name> exists."
            ),
            max_turns=8,
            required_signals=["execute-plan", "Task", "epic"],
        ),
        TurnSpec(
            prompt_template=(
                "Continue the same autonomous execute-plan run.\n"
                "Proceed until all epics are completed or a terminal halted status is explicit.\n"
                "Before stopping, verify and create any missing git artifacts:\n"
                "- branch epic/data-loading\n"
                "- tag tdd-baseline-data-loading\n"
                "- branch epic/model-training\n"
                "- tag tdd-baseline-model-training\n"
                "Report current epic statuses and artifact verification."
            ),
            max_turns=10,
            required_signals=["continue", "status", "epic"],
        ),
    ],
    stop_conditions=["all epics completed or terminal halt"],
)


init_playbook = Playbook(
    name="init",
    turns=[
        TurnSpec(
            prompt_template=(
                "/one-shot-build:init {project_name}\n"
                "If prompted for project name, use {project_name}.\n"
                "Complete scaffolding and commit initial project files."
            ),
            max_turns=5,
            required_signals=["init", "scaffold", "CLAUDE.md"],
        ),
        TurnSpec(
            prompt_template=(
                "Continue the previous init session and finish any remaining scaffold steps.\n"
                "Confirm CLAUDE.md and kyros-agent-workflow/.harnessrc are present."
            ),
            max_turns=5,
            required_signals=["continue", "harnessrc", "CLAUDE.md"],
        ),
    ],
    stop_conditions=["project scaffold complete"],
)
