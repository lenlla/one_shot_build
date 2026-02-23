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
    runner = ClaudeRunner(
        working_dir=project_with_epics,
        timeout=900,  # 15 minutes — execute-plan is the longest phase
        plugin_dir=PLUGIN_DIR,
    )
    prompt = generate_prompt("execute-plan", analyst_context, PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    transcript = runner.run_interactive(prompt, responder=responder.as_callable(), phase_timeout=900)

    log_file = project_with_epics / "execute-plan-transcript.txt"
    _write_transcript(transcript, log_file)

    epics_dir = project_with_epics / "epics" / "v1"
    epic_names = ["data-loading", "model-training"]

    results = check_execute_plan(project_with_epics, epics_dir, epic_names)
    failures, _ = check_results(results)

    if failures:
        failure_msgs = "\n".join(f"  - {r.message}" for r in failures)
        pytest.fail(f"Structural assertions failed:\n{failure_msgs}")


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
