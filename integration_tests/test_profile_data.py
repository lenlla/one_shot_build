"""Integration test for the /profile-data phase.

Runs /profile-data against the synthetic customers.csv and verifies data profiles are created.
"""

import logging
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from integration_tests.agents.setup_agent import generate_prompt
from integration_tests.agents.responder_agent import LiveResponder
from integration_tests.assertions.structural import check_profile_data
from integration_tests.assertions.quality import check_profile_data_quality
from integration_tests.assertions.models import check_results
from integration_tests.claude_runner import ClaudeRunner
from integration_tests.playbooks import profile_data_playbook
from integration_tests.turn_runner import run_turn

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"
INIT_FIXTURE = FIXTURES_DIR / "init_output"
EXPECTED_COLUMNS = ["customer_id", "age", "tenure_months", "monthly_spend", "support_tickets", "churned"]


@pytest.fixture
def analyst_context():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def initialized_project(test_project_dir):
    """A test project pre-loaded with /init output fixture."""
    # Copy init fixture into test project
    for item in INIT_FIXTURE.iterdir():
        dest = test_project_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    # Commit the init state
    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init: scaffold project"],
        cwd=test_project_dir, capture_output=True,
    )
    return test_project_dir


def test_profile_data_structural(initialized_project, analyst_context):
    """Run /profile-data and verify profile files are created."""
    logs_dir = initialized_project / ".integration-logs" / "profile-data"
    turn1 = profile_data_playbook.turns[0]
    turn2 = profile_data_playbook.turns[1]

    first_result = run_turn(
        prompt=turn1.render_prompt(table_path="customers.csv"),
        working_dir=initialized_project,
        plugin_dir=PLUGIN_DIR,
        max_turns=turn1.max_turns,
        timeout=300,
        log_path=logs_dir / "turn-01.log",
    )
    assert first_result.exit_code == 0, f"Initial profile-data turn failed with exit code {first_result.exit_code}"

    last_result = first_result
    failures = []
    for attempt in range(1, 4):
        results = check_profile_data(initialized_project, table_names=["customers"])
        failures, _ = check_results(results)
        if not failures:
            break
        last_result = run_turn(
            prompt=turn2.render_prompt(),
            working_dir=initialized_project,
            plugin_dir=PLUGIN_DIR,
            continue_session=True,
            max_turns=turn2.max_turns,
            timeout=300,
            log_path=logs_dir / f"turn-0{attempt + 1}.log",
        )
        assert last_result.exit_code == 0, f"Profile-data continuation failed with exit code {last_result.exit_code}"

    if failures:
        failure_msgs = "\n".join(f"  - {r.message}" for r in failures)
        pytest.fail(
            "Structural assertions failed after bounded profile-data turns:\n"
            f"{failure_msgs}\n"
            f"last_log={last_result.log_path}"
        )


def test_profile_data_quality(initialized_project, analyst_context):
    """Run /profile-data and check content quality."""
    runner = ClaudeRunner(
        working_dir=initialized_project,
        timeout=300,
        plugin_dir=PLUGIN_DIR,
    )
    prompt = generate_prompt("profile-data", analyst_context, PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    runner.run_interactive(prompt, responder=responder.as_callable())

    results = check_profile_data_quality(
        initialized_project,
        table_names=["customers"],
        expected_columns=EXPECTED_COLUMNS,
    )
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
