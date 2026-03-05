"""Integration test for the /execute-plan phase.

This is the most complex phase — runs the full plan/build/submit loop.
Uses a longer timeout since it involves TDD planning, agent team building, and PR creation.
"""

import logging
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from integration_tests.agents.setup_agent import generate_prompt
from integration_tests.agents.responder_agent import LiveResponder
from integration_tests.assertions.structural import check_execute_plan
from integration_tests.assertions.quality import check_execute_plan_quality
from integration_tests.assertions.models import check_results
from integration_tests.claude_runner import ClaudeRunner
from integration_tests.playbooks import execute_plan_playbook
from integration_tests.turn_runner import run_turn

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"
EPICS_FIXTURE = FIXTURES_DIR / "epics_output"


@pytest.fixture
def analyst_context():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def project_with_epics(test_project_dir):
    """A test project pre-loaded with /init + /profile-data + /define-epics output."""
    for item in EPICS_FIXTURE.iterdir():
        dest = test_project_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    # Set up git remote for PR creation
    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "docs: define epics"],
        cwd=test_project_dir, capture_output=True,
    )
    return test_project_dir


def test_execute_plan_structural(project_with_epics, analyst_context):
    """Run /execute-plan and verify branches, tags, state, and tests pass."""
    build_target = "kyros-agent-workflow/builds/v1"
    _prepare_build_epics(project_with_epics, build_target)
    logs_dir = project_with_epics / ".integration-logs" / "execute-plan"
    turn1 = execute_plan_playbook.turns[0]
    turn2 = execute_plan_playbook.turns[1]
    first_result = run_turn(
        prompt=turn1.render_prompt(build_target=build_target),
        working_dir=project_with_epics,
        plugin_dir=PLUGIN_DIR,
        max_turns=turn1.max_turns,
        timeout=900,
        log_path=logs_dir / "turn-01.log",
    )
    assert first_result.exit_code == 0, f"Initial execute-plan turn failed with exit code {first_result.exit_code}"

    epics_dir = project_with_epics / "epics" / "v1"
    epic_names = ["data-loading", "model-training"]
    observed_subagent_signal = _has_subagent_signal(first_result.tool_events, first_result.assistant_texts)

    failures = []
    last_result = first_result
    for attempt in range(1, 13):
        results = check_execute_plan(project_with_epics, epics_dir, epic_names)
        failures, _ = check_results(results)
        if not failures:
            break
        last_result = run_turn(
            prompt=turn2.render_prompt(),
            working_dir=project_with_epics,
            plugin_dir=PLUGIN_DIR,
            continue_session=True,
            max_turns=turn2.max_turns,
            timeout=900,
            log_path=logs_dir / f"turn-0{attempt + 1}.log",
        )
        assert last_result.exit_code == 0, f"Execute-plan continuation failed with exit code {last_result.exit_code}"
        if _has_subagent_signal(last_result.tool_events, last_result.assistant_texts):
            observed_subagent_signal = True

    if failures:
        failure_msgs = "\n".join(f"  - {r.message}" for r in failures)
        signal_note = (
            "observed_subagent_signal=true"
            if observed_subagent_signal
            else "observed_subagent_signal=false"
        )
        pytest.fail(
            "Structural assertions failed after bounded execute-plan turns:\n"
            f"{failure_msgs}\n"
            f"{signal_note}\n"
            f"last_log={last_result.log_path}"
        )


def test_execute_plan_quality(project_with_epics, analyst_context):
    """Run /execute-plan and check content quality."""
    runner = ClaudeRunner(
        working_dir=project_with_epics,
        timeout=900,
        plugin_dir=PLUGIN_DIR,
    )
    prompt = generate_prompt("execute-plan", analyst_context, PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    runner.run_interactive(prompt, responder=responder.as_callable(), phase_timeout=900)

    epics_dir = project_with_epics / "epics" / "v1"
    epic_names = ["data-loading", "model-training"]

    results = check_execute_plan_quality(project_with_epics, epics_dir, epic_names)
    _, warnings = check_results(results)

    if warnings:
        warning_msgs = "\n".join(f"  - {r.message}" for r in warnings)
        logger.warning("Quality warnings:\n%s", warning_msgs)


def _write_transcript(transcript, path):
    with open(path, "w") as f:
        for turn in transcript.turns:
            f.write(f"=== {turn['role'].upper()} ===\n")
            f.write(turn["content"])
            f.write("\n\n")


def _prepare_build_epics(project_dir: Path, build_target: str) -> None:
    source_dir = project_dir / "epics" / "v1"
    target_dir = project_dir / build_target / "epic-specs"
    target_dir.mkdir(parents=True, exist_ok=True)
    for source in source_dir.glob("*.yaml"):
        shutil.copy2(source, target_dir / source.name)


def _has_subagent_signal(tool_events: list[dict], assistant_texts: list[str]) -> bool:
    for event in tool_events:
        name = event.get("name")
        if name in {"Task", "Agent"}:
            return True
    haystack = " ".join(assistant_texts).lower()
    return "sub-agent" in haystack or "dispatch" in haystack
