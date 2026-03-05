"""Strict circuit-breaker integration tests using deterministic multi-turn execution."""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from integration_tests.playbooks import circuit_breaker_playbook
from integration_tests.turn_runner import TurnResult
from integration_tests.turn_runner import run_turn

PLUGIN_DIR = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"

TERMINAL_STATUS_TOKENS = (
    "halt",
    "block",
    "fail",
    "error",
    "stop",
    "terminal",
    "rejected",
)
SUCCESS_STATUS_TOKENS = ("complete", "success", "done")
BREAKER_SIGNAL_TOKENS = (
    "circuit breaker",
    "no progress",
    "same error",
    "review rounds",
    "halt",
    "stopping",
    "cannot progress",
)


@pytest.fixture
def analyst_context():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        return yaml.safe_load(f)


def _setup_project_with_epic(
    test_project_dir,
    epic_spec: dict,
    epic_filename: str = "01-test-epic.yaml",
    test_command: str | None = None,
):
    """Set up initialized project with low breaker thresholds and a single test epic."""
    epics_fixture = FIXTURES_DIR / "epics_output"
    for item in epics_fixture.iterdir():
        dest = test_project_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    harnessrc = test_project_dir / "kyros-agent-workflow" / ".harnessrc"
    config = {
        "circuit_breaker": {
            "no_progress_threshold": 1,
            "same_error_threshold": 1,
            "max_review_rounds": 1,
        },
        "agent_team": {
            "developer_model": "haiku",
            "reviewer_model": "haiku",
        },
    }
    if test_command:
        config["testing"] = {"test_command": test_command}
    with open(harnessrc, "w") as f:
        yaml.dump(config, f)

    epics_dir = test_project_dir / "epics" / "v1"
    epics_dir.mkdir(parents=True, exist_ok=True)
    for existing in epics_dir.glob("*.yaml"):
        existing.unlink()
    with open(epics_dir / epic_filename, "w") as f:
        yaml.dump(epic_spec, f)

    build_epics_dir = test_project_dir / "kyros-agent-workflow" / "builds" / "v1" / "epic-specs"
    build_epics_dir.mkdir(parents=True, exist_ok=True)
    for existing in build_epics_dir.glob("*.yaml"):
        existing.unlink()
    shutil.copy2(epics_dir / epic_filename, build_epics_dir / epic_filename)

    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "setup test epic"], cwd=test_project_dir, capture_output=True)

    return {
        "epic_name": epic_spec["name"],
        "build_target": "kyros-agent-workflow/builds/v1",
        "state_candidates": [
            build_epics_dir / ".execution-state.yaml",
            build_epics_dir.parent / ".execution-state.yaml",
            epics_dir / ".execution-state.yaml",
        ],
    }


def _run_circuit_scenario(
    test_project_dir: Path,
    scenario_name: str,
    config: dict,
    max_continue_turns: int = 3,
) -> tuple[str, bool, list[str], TurnResult]:
    """Run bounded continuation loop and return status + diagnostics."""
    logs_dir = test_project_dir / ".integration-logs" / f"circuit-{scenario_name}"
    turn1 = circuit_breaker_playbook.turns[0]
    turn2 = circuit_breaker_playbook.turns[1]

    last_result = run_turn(
        prompt=turn1.render_prompt(target=config["build_target"]),
        working_dir=test_project_dir,
        plugin_dir=PLUGIN_DIR,
        max_turns=turn1.max_turns,
        timeout=300,
        log_path=logs_dir / "turn-01.log",
    )

    collected_texts = list(last_result.assistant_texts)
    status = _read_epic_status(config["state_candidates"], config["epic_name"])
    if _is_terminal_status(status):
        return status, _has_breaker_signal(collected_texts), collected_texts, last_result

    for index in range(1, max_continue_turns + 1):
        last_result = run_turn(
            prompt=turn2.render_prompt(target=config["build_target"]),
            working_dir=test_project_dir,
            plugin_dir=PLUGIN_DIR,
            continue_session=True,
            max_turns=turn2.max_turns,
            timeout=300,
            log_path=logs_dir / f"turn-{index + 1:02d}.log",
        )
        collected_texts.extend(last_result.assistant_texts)
        status = _read_epic_status(config["state_candidates"], config["epic_name"])
        if _is_terminal_status(status):
            break

    breaker_signal = _has_breaker_signal(collected_texts)
    return status, breaker_signal, collected_texts, last_result


def _read_epic_status(state_candidates: list[Path], epic_name: str) -> str:
    for state_file in state_candidates:
        if not state_file.exists():
            continue
        with open(state_file) as f:
            state = yaml.safe_load(f) or {}
        if not isinstance(state, dict):
            continue
        epics = state.get("epics", {})
        if isinstance(epics, dict):
            epic_state = epics.get(epic_name, {})
            if isinstance(epic_state, dict):
                status = epic_state.get("status")
                if isinstance(status, str):
                    return status
        if isinstance(epics, list):
            for epic in epics:
                if not isinstance(epic, dict):
                    continue
                if epic.get("name") != epic_name:
                    continue
                status = epic.get("status")
                if isinstance(status, str):
                    return status
    return ""


def _has_breaker_signal(assistant_texts: list[str]) -> bool:
    haystack = " ".join(assistant_texts).lower()
    return any(token in haystack for token in BREAKER_SIGNAL_TOKENS)


def _is_terminal_status(status: str) -> bool:
    lowered = status.lower()
    return any(token in lowered for token in TERMINAL_STATUS_TOKENS)


def _is_success_status(status: str) -> bool:
    lowered = status.lower()
    return any(token in lowered for token in SUCCESS_STATUS_TOKENS)


def _diagnostic_message(status: str, breaker_signal: bool, texts: list[str], result: TurnResult) -> str:
    excerpt = " ".join(texts)[-400:].replace("\n", " ")
    event_names = [event.get("name", "<unknown>") for event in result.tool_events[-8:]]
    return (
        f"status={status!r}, breaker_signal={breaker_signal}, "
        f"last_tool_events={event_names}, "
        f"last_text_excerpt={excerpt}, "
        f"last_log={result.log_path}"
    )


def test_no_progress_halts(test_project_dir, analyst_context):
    """Impossible acceptance criteria should terminate via breaker safeguards."""
    epic = {
        "name": "impossible-accuracy",
        "description": "Achieve impossibly high accuracy on a tiny dataset",
        "acceptance_criteria": [
            "Model achieves 99.9% accuracy on test set with zero false positives and zero false negatives"
        ],
        "dependencies": [],
        "estimated_steps": 2,
    }
    config = _setup_project_with_epic(test_project_dir, epic)

    status, breaker_signal, texts, result = _run_circuit_scenario(test_project_dir, "no-progress", config)

    assert _is_terminal_status(status) or breaker_signal, _diagnostic_message(status, breaker_signal, texts, result)
    assert not _is_success_status(status), _diagnostic_message(status, breaker_signal, texts, result)


def test_repeated_error_halts(test_project_dir, analyst_context):
    """Broken dependency criteria should terminate via repeated-error safeguards."""
    epic = {
        "name": "broken-import",
        "description": "Simple implementation that will repeatedly fail due to broken test command",
        "acceptance_criteria": [
            "Create a function that returns the string 'ok'",
            "Add a unit test covering the function",
        ],
        "dependencies": [],
        "estimated_steps": 1,
    }
    config = _setup_project_with_epic(
        test_project_dir,
        epic,
        test_command="definitely_not_a_real_test_command_12345",
    )

    status, breaker_signal, texts, result = _run_circuit_scenario(test_project_dir, "same-error", config)

    assert _is_terminal_status(status) or breaker_signal, _diagnostic_message(status, breaker_signal, texts, result)
    assert not _is_success_status(status), _diagnostic_message(status, breaker_signal, texts, result)


def test_review_rounds_exceeded(test_project_dir, analyst_context):
    """Vague acceptance criteria should hit review-round safeguards and terminate."""
    epic = {
        "name": "vague-criteria",
        "description": "An epic with criteria too vague for the reviewer to ever approve",
        "acceptance_criteria": [
            "Code must be elegant and beautiful",
            "Implementation must demonstrate deep understanding of the problem domain",
            "Solution must be the most optimal possible approach",
        ],
        "dependencies": [],
        "estimated_steps": 1,
    }
    config = _setup_project_with_epic(test_project_dir, epic)

    status, breaker_signal, texts, result = _run_circuit_scenario(test_project_dir, "review-rounds", config)

    assert _is_terminal_status(status) or breaker_signal, _diagnostic_message(status, breaker_signal, texts, result)
    assert not _is_success_status(status), _diagnostic_message(status, breaker_signal, texts, result)
