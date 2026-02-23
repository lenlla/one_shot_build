"""Fix agent — autonomous diagnose-fix-verify cycle for integration test failures.

When a structural assertion fails, this agent:
1. Collects failure context (assertion messages, transcript, relevant plugin source)
2. Launches a Claude session pointed at the plugin repo to diagnose and fix
3. Changes land on a fix branch for human review
"""

import datetime
import logging
import subprocess
from pathlib import Path

from integration_tests.assertions.models import AssertionResult
from integration_tests.claude_runner import ClaudeRunner

logger = logging.getLogger(__name__)


PHASE_SKILL_MAP = {
    "init": "skills/harness-init/SKILL.md",
    "profile-data": "skills/profile-data/SKILL.md",
    "define-epics": "skills/define-epics/SKILL.md",
    "execute-plan": "skills/execute-plan/SKILL.md",
}

ALLOWED_DIRS = ["skills", "commands", "hooks", "templates", "agents", "lib"]


def collect_failure_context(
    test_name: str,
    phase: str,
    failures: list[AssertionResult],
    transcript_path: Path | None,
    project_dir: Path,
    plugin_dir: Path,
) -> str:
    """Assemble the diagnostic context for the fix agent."""
    parts = [
        f"# Integration Test Failure Report",
        f"",
        f"**Test:** {test_name}",
        f"**Phase:** {phase}",
        f"",
        f"## Failed Assertions",
        "",
    ]
    for f in failures:
        parts.append(f"- {f.message}")

    parts.extend(["", "## Relevant Skill", ""])
    skill_path = plugin_dir / PHASE_SKILL_MAP.get(phase, "")
    if skill_path.is_file():
        parts.append(f"File: {PHASE_SKILL_MAP[phase]}")
        parts.append("```")
        parts.append(skill_path.read_text()[:5000])  # Truncate if very long
        parts.append("```")

    if transcript_path and transcript_path.is_file():
        parts.extend(["", "## Session Transcript (last 3000 chars)", ""])
        transcript = transcript_path.read_text()
        parts.append("```")
        parts.append(transcript[-3000:])
        parts.append("```")

    parts.extend(["", "## Test Project State", ""])
    # List files in the project dir
    try:
        result = subprocess.run(
            ["find", ".", "-type", "f", "-not", "-path", "./.git/*"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        parts.append("```")
        parts.append(result.stdout[:2000])
        parts.append("```")
    except Exception:
        parts.append("(could not list project files)")

    return "\n".join(parts)


class FixAgent:
    """Launches a Claude session to fix plugin code based on failure context."""

    def __init__(self, plugin_dir: Path, timeout: int = 300):
        self.plugin_dir = plugin_dir
        self.timeout = timeout

    def attempt_fix(self, failure_context: str, phase: str) -> dict:
        """Run a fix attempt. Returns a dict with branch name and success status."""
        branch = self._branch_name(phase)

        # Create fix branch
        subprocess.run(
            ["git", "checkout", "-b", branch],
            cwd=self.plugin_dir,
            capture_output=True,
        )

        try:
            runner = ClaudeRunner(working_dir=self.plugin_dir, timeout=self.timeout)
            prompt = (
                f"An integration test for the one-shot-build plugin failed. "
                f"Diagnose the issue and fix the plugin code.\n\n"
                f"IMPORTANT CONSTRAINTS:\n"
                f"- Only modify files under: {', '.join(ALLOWED_DIRS)}\n"
                f"- Do NOT modify any files under integration_tests/\n"
                f"- Commit your fixes with a descriptive message\n\n"
                f"{failure_context}"
            )
            output = runner.run_print(prompt)

            # Check if any files were modified
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=self.plugin_dir,
                capture_output=True,
                text=True,
            )
            files_changed = [f for f in result.stdout.strip().split("\n") if f]
            all_allowed = all(self._is_allowed_path(self.plugin_dir / f) for f in files_changed)

            return {
                "branch": branch,
                "files_changed": files_changed,
                "all_allowed": all_allowed,
                "output": output,
            }
        except Exception as e:
            logger.error("Fix attempt failed: %s", e)
            return {"branch": branch, "files_changed": [], "all_allowed": True, "output": str(e)}
        finally:
            # Return to main branch
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=self.plugin_dir,
                capture_output=True,
            )

    def _branch_name(self, phase: str) -> str:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"fix/integration-{phase}-{ts}"

    def _is_allowed_path(self, path: Path) -> bool:
        try:
            rel = path.relative_to(self.plugin_dir)
        except ValueError:
            return False
        top_dir = str(rel).split("/")[0]
        return top_dir in ALLOWED_DIRS
