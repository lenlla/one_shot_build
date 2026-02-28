"""Tests for deterministic multi-turn test playbooks."""

from integration_tests.playbooks import (
    Playbook,
    TurnSpec,
    circuit_breaker_playbook,
    define_epics_playbook,
    resume_playbook,
)


def test_turn_spec_renders_prompt_template():
    turn = TurnSpec(
        prompt_template="/define-epics {target}",
        max_turns=2,
        required_signals=["Skill", "TodoWrite"],
    )

    rendered = turn.render_prompt(target="kyros-agent-workflow/builds/v1/epic-specs")

    assert rendered == "/define-epics kyros-agent-workflow/builds/v1/epic-specs"


def test_define_epics_playbook_has_two_deterministic_turns():
    assert define_epics_playbook.name == "define-epics"
    assert len(define_epics_playbook.turns) == 2
    assert define_epics_playbook.turns[0].max_turns >= 2
    assert define_epics_playbook.turns[1].max_turns >= 2
    assert "Skill" in define_epics_playbook.turns[0].required_signals
    first_prompt = define_epics_playbook.turns[0].render_prompt(build_path="kyros-agent-workflow/builds/v1")
    assert first_prompt.startswith("/define-epics ")


def test_resume_playbook_requires_continue_flow():
    assert resume_playbook.name == "resume"
    assert len(resume_playbook.turns) == 2
    first_prompt = resume_playbook.turns[0].render_prompt(target="epics/v1")
    assert first_prompt.startswith("/execute-plan ")
    assert any("continue" in signal.lower() for signal in resume_playbook.turns[1].required_signals)


def test_circuit_breaker_playbook_has_stop_conditions():
    assert isinstance(circuit_breaker_playbook, Playbook)
    first_prompt = circuit_breaker_playbook.turns[0].render_prompt(target="kyros-agent-workflow/builds/v1")
    assert first_prompt.startswith("/one-shot-build:execute-plan-autonomously ")
    assert circuit_breaker_playbook.stop_conditions
    assert "terminal" in " ".join(circuit_breaker_playbook.stop_conditions).lower()
