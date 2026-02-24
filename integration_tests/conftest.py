"""Shared pytest fixtures for integration tests."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

from integration_tests.claude_runner import ClaudeRunner


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"
PLUGIN_DIR = Path(__file__).parent.parent  # one_shot_build repo root


def pytest_addoption(parser):
    parser.addoption("--chained", action="store_true", default=False, help="Run phases chained in a shared directory")
    parser.addoption("--phase-timeout", type=int, default=600, help="Timeout per phase in seconds")
    parser.addoption("--no-fix", action="store_true", default=False, help="Skip fix-then-retry loop")


@pytest.fixture(scope="function")
def test_project_dir(tmp_path):
    """A fresh temp directory with git init and synthetic data copied in."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    shutil.copy(FIXTURES_DIR / "customers.csv", project_dir / "customers.csv")
    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial: add synthetic data"],
        cwd=project_dir, capture_output=True,
    )
    return project_dir


@pytest.fixture(scope="session")
def shared_project_dir(tmp_path_factory):
    """A shared temp directory for chained mode — persists across all tests in the session."""
    project_dir = tmp_path_factory.mktemp("chained-project")
    shutil.copy(FIXTURES_DIR / "customers.csv", project_dir / "customers.csv")
    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial: add synthetic data"],
        cwd=project_dir, capture_output=True,
    )
    return project_dir


@pytest.fixture
def claude_runner(test_project_dir, request):
    """A ClaudeRunner pointed at the test project directory."""
    timeout = request.config.getoption("--phase-timeout")
    return ClaudeRunner(
        working_dir=test_project_dir,
        timeout=timeout,
        plugin_dir=PLUGIN_DIR,
    )


@pytest.fixture
def analyst_context():
    """The pre-built analyst answers as a dict."""
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def log_dir(tmp_path):
    """Directory for session transcripts."""
    d = tmp_path / ".logs"
    d.mkdir()
    return d
