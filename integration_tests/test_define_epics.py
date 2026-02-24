"""Integration test for the /define-epics phase.

Runs /define-epics and verifies epic YAML specs are created.
"""

import logging
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from integration_tests.agents.setup_agent import generate_prompt
from integration_tests.agents.responder_agent import LiveResponder
from integration_tests.assertions.structural import check_define_epics
from integration_tests.assertions.quality import check_define_epics_quality
from integration_tests.assertions.models import check_results
from integration_tests.claude_runner import ClaudeRunner

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"
PROFILE_FIXTURE = FIXTURES_DIR / "profile_output"


@pytest.fixture
def analyst_context():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def profiled_project(test_project_dir):
    """A test project pre-loaded with /init + /profile-data output."""
    for item in PROFILE_FIXTURE.iterdir():
        dest = test_project_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "docs: add data profiles"],
        cwd=test_project_dir, capture_output=True,
    )
    return test_project_dir


def test_define_epics_structural(profiled_project, analyst_context):
    """Run /define-epics and verify epic specs are created."""
    runner = ClaudeRunner(
        working_dir=profiled_project,
        timeout=300,
        plugin_dir=PLUGIN_DIR,
    )
    prompt = generate_prompt("define-epics", analyst_context, PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    transcript = runner.run_interactive(prompt, responder=responder.as_callable())

    log_file = profiled_project / "define-epics-transcript.txt"
    _write_transcript(transcript, log_file)

    # Find the epics directory — we don't know the exact name in advance
    epics_dir = _find_epics_dir(profiled_project)
    if epics_dir is None:
        pytest.fail("No epics directory found after /define-epics")

    results = check_define_epics(profiled_project, epics_dir)
    failures, _ = check_results(results)

    if failures:
        failure_msgs = "\n".join(f"  - {r.message}" for r in failures)
        pytest.fail(f"Structural assertions failed:\n{failure_msgs}")


def test_define_epics_quality(profiled_project, analyst_context):
    """Run /define-epics and check content quality."""
    runner = ClaudeRunner(
        working_dir=profiled_project,
        timeout=300,
        plugin_dir=PLUGIN_DIR,
    )
    prompt = generate_prompt("define-epics", analyst_context, PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    runner.run_interactive(prompt, responder=responder.as_callable())

    epics_dir = _find_epics_dir(profiled_project)
    if epics_dir is None:
        logger.warning("No epics directory found — skipping quality checks")
        return

    results = check_define_epics_quality(epics_dir)
    _, warnings = check_results(results)

    if warnings:
        warning_msgs = "\n".join(f"  - {r.message}" for r in warnings)
        logger.warning("Quality warnings:\n%s", warning_msgs)


def _find_epics_dir(project_dir: Path) -> Path | None:
    """Search for the epics directory created by /define-epics."""
    # Check common locations
    for candidate in ["epics/v1", "epics/initial", "epics"]:
        d = project_dir / candidate
        if d.is_dir() and list(d.glob("*.yaml")):
            return d
    # Search more broadly
    for d in project_dir.rglob("*.yaml"):
        parent = d.parent
        yaml_files = list(parent.glob("*.yaml"))
        if len(yaml_files) >= 2 and parent.name != "kyros-agent-workflow":
            return parent
    return None


def _write_transcript(transcript, path):
    with open(path, "w") as f:
        for turn in transcript.turns:
            f.write(f"=== {turn['role'].upper()} ===\n")
            f.write(turn["content"])
            f.write("\n\n")
