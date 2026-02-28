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
