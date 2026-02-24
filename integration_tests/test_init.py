"""Integration test for the /init phase.

Runs /init via the claude CLI and verifies the project scaffolding was created correctly.
"""

import logging
from pathlib import Path

import pytest
import yaml

from integration_tests.agents.setup_agent import generate_prompt
from integration_tests.agents.responder_agent import LiveResponder
from integration_tests.assertions.structural import check_init
from integration_tests.assertions.quality import check_init_quality
from integration_tests.assertions.models import check_results
from integration_tests.claude_runner import ClaudeRunner

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"


@pytest.fixture
def analyst_context():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        return yaml.safe_load(f)


def test_init_structural(test_project_dir, analyst_context):
    """Run /init and verify all required files and directories are created."""
    runner = ClaudeRunner(
        working_dir=test_project_dir,
        timeout=120,
        plugin_dir=PLUGIN_DIR,
    )
    prompt = generate_prompt("init", analyst_context, PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    transcript = runner.run_interactive(prompt, responder=responder.as_callable())

    # Log transcript for debugging
    log_file = test_project_dir / "init-transcript.txt"
    _write_transcript(transcript, log_file)

    # Structural assertions (hard gate)
    results = check_init(test_project_dir)
    failures, warnings = check_results(results)

    if failures:
        failure_msgs = "\n".join(f"  - {r.message}" for r in failures)
        pytest.fail(f"Structural assertions failed:\n{failure_msgs}")


def test_init_quality(test_project_dir, analyst_context):
    """Run /init and check content quality (advisory)."""
    runner = ClaudeRunner(
        working_dir=test_project_dir,
        timeout=120,
        plugin_dir=PLUGIN_DIR,
    )
    prompt = generate_prompt("init", analyst_context, PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    transcript = runner.run_interactive(prompt, responder=responder.as_callable())

    results = check_init_quality(test_project_dir, project_name=analyst_context["project_name"])
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
        if transcript.timed_out:
            f.write("=== TIMED OUT ===\n")
