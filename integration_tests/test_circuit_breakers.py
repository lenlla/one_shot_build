"""Edge-case tests for circuit breaker behavior.

These tests deliberately induce failure conditions and verify the harness halts correctly.
Uses low thresholds in .harnessrc to keep test runtime short.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from integration_tests.agents.responder_agent import LiveResponder
from integration_tests.claude_runner import ClaudeRunner

PLUGIN_DIR = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"


@pytest.fixture
def analyst_context():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        return yaml.safe_load(f)


def _setup_project_with_epic(test_project_dir, epic_spec: dict, epic_filename: str = "01-test-epic.yaml"):
    """Helper: set up an initialized project with a single epic and low circuit breaker thresholds."""
    epics_fixture = FIXTURES_DIR / "epics_output"
    for item in epics_fixture.iterdir():
        dest = test_project_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    # Override harnessrc with low thresholds
    harnessrc = test_project_dir / "kyros-agent-workflow" / ".harnessrc"
    config = {
        "circuit_breaker": {
            "no_progress_threshold": 2,
            "same_error_threshold": 2,
            "max_review_rounds": 2,
        },
        "agent_team": {
            "developer_model": "haiku",
            "reviewer_model": "haiku",
        },
    }
    with open(harnessrc, "w") as f:
        yaml.dump(config, f)

    # Replace epics with our test epic
    epics_dir = test_project_dir / "epics" / "v1"
    epics_dir.mkdir(parents=True, exist_ok=True)
    for existing in epics_dir.glob("*.yaml"):
        existing.unlink()
    with open(epics_dir / epic_filename, "w") as f:
        yaml.dump(epic_spec, f)

    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "setup test epic"], cwd=test_project_dir, capture_output=True)
    return epics_dir


def test_no_progress_halts(test_project_dir, analyst_context):
    """An impossible acceptance criterion should trigger the no-progress circuit breaker."""
    epic = {
        "name": "impossible-accuracy",
        "description": "Achieve impossibly high accuracy on a tiny dataset",
        "acceptance_criteria": [
            "Model achieves 99.9% accuracy on test set with zero false positives and zero false negatives"
        ],
        "dependencies": [],
        "estimated_steps": 2,
    }
    epics_dir = _setup_project_with_epic(test_project_dir, epic)

    runner = ClaudeRunner(working_dir=test_project_dir, timeout=600, plugin_dir=PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    transcript = runner.run_interactive(
        "/execute-plan epics/v1",
        responder=responder.as_callable(),
        phase_timeout=600,
    )

    # Verify the harness stopped — check execution state
    state_file = epics_dir / ".execution-state.yaml"
    if state_file.exists():
        with open(state_file) as f:
            state = yaml.safe_load(f) or {}
        epic_state = state.get("epics", {}).get("impossible-accuracy", {})
        status = epic_state.get("status", "")
        # Should be blocked or have circuit breaker info
        assert status != "completed", f"Epic should not have completed — status is '{status}'"


def test_repeated_error_halts(test_project_dir, analyst_context):
    """A broken dependency should trigger the repeated-error circuit breaker."""
    epic = {
        "name": "broken-import",
        "description": "An epic that requires a nonexistent library",
        "acceptance_criteria": [
            "Code imports and uses nonexistent_lib.magic_function()",
            "Unit test verifies magic_function returns expected output",
        ],
        "dependencies": [],
        "estimated_steps": 2,
    }
    epics_dir = _setup_project_with_epic(test_project_dir, epic)

    runner = ClaudeRunner(working_dir=test_project_dir, timeout=600, plugin_dir=PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    transcript = runner.run_interactive(
        "/execute-plan epics/v1",
        responder=responder.as_callable(),
        phase_timeout=600,
    )

    state_file = epics_dir / ".execution-state.yaml"
    if state_file.exists():
        with open(state_file) as f:
            state = yaml.safe_load(f) or {}
        epic_state = state.get("epics", {}).get("broken-import", {})
        status = epic_state.get("status", "")
        assert status != "completed", f"Epic should not have completed — status is '{status}'"


def test_review_rounds_exceeded(test_project_dir, analyst_context):
    """A vague acceptance criterion should trigger max review rounds."""
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
    epics_dir = _setup_project_with_epic(test_project_dir, epic)

    runner = ClaudeRunner(working_dir=test_project_dir, timeout=600, plugin_dir=PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    transcript = runner.run_interactive(
        "/execute-plan epics/v1",
        responder=responder.as_callable(),
        phase_timeout=600,
    )

    state_file = epics_dir / ".execution-state.yaml"
    if state_file.exists():
        with open(state_file) as f:
            state = yaml.safe_load(f) or {}
        epic_state = state.get("epics", {}).get("vague-criteria", {})
        status = epic_state.get("status", "")
        assert status != "completed", f"Epic should not have completed — status is '{status}'"
