"""Tests for the fix agent — verifies failure context collection and branch management."""

from pathlib import Path

from integration_tests.agents.fix_agent import collect_failure_context, FixAgent
from integration_tests.assertions.models import AssertionResult


PLUGIN_DIR = Path(__file__).parent.parent.parent


def test_collect_failure_context():
    failures = [
        AssertionResult(passed=False, message="CLAUDE.md not found", tier="structural"),
        AssertionResult(passed=False, message=".harnessrc not found", tier="structural"),
    ]
    context = collect_failure_context(
        test_name="test_init_structural",
        phase="init",
        failures=failures,
        transcript_path=None,
        project_dir=Path("/tmp/fake"),
        plugin_dir=PLUGIN_DIR,
    )
    assert "test_init_structural" in context
    assert "CLAUDE.md not found" in context
    assert "harness-init" in context  # Should include the relevant skill


def test_fix_agent_creates_branch(tmp_path):
    """Verify the fix agent creates a properly named branch."""
    agent = FixAgent(plugin_dir=tmp_path, timeout=5)
    branch_name = agent._branch_name("init")
    assert branch_name.startswith("fix/integration-init-")


def test_fix_agent_allowed_paths():
    """Verify the fix agent only allows modifications to safe directories."""
    agent = FixAgent(plugin_dir=PLUGIN_DIR, timeout=5)
    assert agent._is_allowed_path(PLUGIN_DIR / "skills" / "harness-init" / "SKILL.md")
    assert agent._is_allowed_path(PLUGIN_DIR / "hooks" / "session-start.sh")
    assert agent._is_allowed_path(PLUGIN_DIR / "templates" / "CLAUDE.md.template")
    assert not agent._is_allowed_path(PLUGIN_DIR / "integration_tests" / "test_init.py")
    assert not agent._is_allowed_path(PLUGIN_DIR / "package.json")
