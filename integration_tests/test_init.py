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
from integration_tests.playbooks import init_playbook
from integration_tests.turn_runner import run_turn

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"


@pytest.fixture
def analyst_context():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        return yaml.safe_load(f)


def test_init_structural(test_project_dir, analyst_context):
    """Run /init and verify all required files and directories are created."""
    logs_dir = test_project_dir / ".integration-logs" / "init"
    turn1 = init_playbook.turns[0]
    turn2 = init_playbook.turns[1]
    first_result = run_turn(
        prompt=turn1.render_prompt(project_name=analyst_context["project_name"]),
        working_dir=test_project_dir,
        plugin_dir=PLUGIN_DIR,
        max_turns=turn1.max_turns,
        timeout=180,
        log_path=logs_dir / "turn-01.log",
    )
    assert first_result.exit_code == 0, f"Initial init turn failed with exit code {first_result.exit_code}"

    failures = []
    last_result = first_result
    for attempt in range(1, 4):
        results = check_init(test_project_dir)
        failures, _ = check_results(results)
        if not failures:
            break
        last_result = run_turn(
            prompt=turn2.render_prompt(),
            working_dir=test_project_dir,
            plugin_dir=PLUGIN_DIR,
            continue_session=True,
            max_turns=turn2.max_turns,
            timeout=180,
            log_path=logs_dir / f"turn-0{attempt + 1}.log",
        )
        assert last_result.exit_code == 0, f"Init continuation failed with exit code {last_result.exit_code}"
    final_results = check_init(test_project_dir)
    failures, _ = check_results(final_results)

    if failures:
        failure_msgs = "\n".join(f"  - {r.message}" for r in failures)
        pytest.fail(
            "Structural assertions failed after bounded init turns:\n"
            f"{failure_msgs}\n"
            f"last_log={last_result.log_path}"
        )


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
