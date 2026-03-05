"""Edge-case tests for input validation and guard behavior."""

import subprocess
from pathlib import Path

import pytest
import yaml

from integration_tests.claude_runner import ClaudeRunner

PLUGIN_DIR = Path(__file__).parent.parent


def test_missing_epics_dir(test_project_dir):
    """Calling /execute-plan with a nonexistent path should error gracefully."""
    runner = ClaudeRunner(working_dir=test_project_dir, timeout=60, plugin_dir=PLUGIN_DIR)
    output = runner.run_print("/execute-plan nonexistent/path")
    # Should get an error message, not a crash
    assert len(output) > 0
    # Should NOT create a state file
    state_file = test_project_dir / "nonexistent" / "path" / ".execution-state.yaml"
    assert not state_file.exists()


def test_malformed_harnessrc(test_project_dir):
    """A malformed .harnessrc should produce a config error."""
    harness_dir = test_project_dir / "kyros-agent-workflow"
    harness_dir.mkdir(exist_ok=True)
    (harness_dir / ".harnessrc").write_text("{{{{invalid yaml: [[[")
    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add bad config"], cwd=test_project_dir, capture_output=True)

    runner = ClaudeRunner(working_dir=test_project_dir, timeout=60, plugin_dir=PLUGIN_DIR)
    output = runner.run_print("/harness-status")
    # The harness should handle this gracefully
    assert len(output) > 0


def test_concurrent_execution_warning(test_project_dir):
    """An existing in-progress execution should trigger a warning."""
    # Set up a fake active execution
    epics_dir = test_project_dir / "epics" / "v1"
    epics_dir.mkdir(parents=True)
    state = {
        "started_at": "2026-02-19T10:00:00Z",
        "mode": "interactive",
        "epics": {"fake-epic": {"status": "building"}},
    }
    with open(epics_dir / ".execution-state.yaml", "w") as f:
        yaml.dump(state, f)
    # Also need a CLAUDE.md and kyros-agent-workflow for the harness to recognize this as a project
    (test_project_dir / "kyros-agent-workflow").mkdir(exist_ok=True)
    (test_project_dir / "CLAUDE.md").write_text("<!-- begin:one-shot-build -->\ntest\n<!-- end:one-shot-build -->")
    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add fake state"], cwd=test_project_dir, capture_output=True)

    runner = ClaudeRunner(working_dir=test_project_dir, timeout=120, plugin_dir=PLUGIN_DIR)
    # Start a new execution — should warn about the existing one
    output = runner.run_print("/harness-status")
    lower = output.lower()
    assert "active" in lower or "execution" in lower or "in progress" in lower or "building" in lower


def test_empty_data_file(test_project_dir):
    """Profiling an empty CSV (headers only) should handle gracefully."""
    # Create headers-only CSV
    (test_project_dir / "empty.csv").write_text("customer_id,age,tenure_months,monthly_spend,support_tickets,churned\n")
    # Set up initialized project
    harness_dir = test_project_dir / "kyros-agent-workflow"
    harness_dir.mkdir(exist_ok=True)
    (harness_dir / ".harnessrc").write_text("circuit_breaker:\n  no_progress_threshold: 3\n")
    (test_project_dir / "CLAUDE.md").write_text("<!-- begin:one-shot-build -->\ntest\n<!-- end:one-shot-build -->")
    for d in ["docs/context", "docs/standards", "docs/solutions"]:
        (harness_dir / d).mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=test_project_dir, capture_output=True)

    runner = ClaudeRunner(working_dir=test_project_dir, timeout=120, plugin_dir=PLUGIN_DIR)
    output = runner.run_print("/profile-data empty.csv")
    # Should not crash — should either report the issue or produce a profile noting 0 rows
    assert len(output) > 0
