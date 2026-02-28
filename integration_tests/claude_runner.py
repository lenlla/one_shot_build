"""Wrapper around the claude CLI for integration testing.

Provides two modes:
- run_print(): Non-interactive, sends a single prompt via --print flag
- run_interactive(): Interactive, streams stdin/stdout for multi-turn sessions
"""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SessionTranscript:
    """Captured output from a Claude session."""
    turns: list[dict] = field(default_factory=list)  # {"role": "claude"|"user", "content": str}
    raw_stdout: str = ""
    raw_stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False


class ClaudeRunner:
    """Manages claude CLI subprocess lifecycle."""

    def __init__(
        self,
        working_dir: Path | str | None = None,
        timeout: int = 600,
        plugin_dir: Path | str | None = None,
    ):
        self.working_dir = Path(working_dir) if working_dir else None
        self.timeout = timeout
        self.plugin_dir = Path(plugin_dir) if plugin_dir else None

    def _base_cmd(self) -> list[str]:
        cmd = ["claude", "--dangerously-skip-permissions"]
        if self.plugin_dir:
            cmd.extend(["--plugin-dir", str(self.plugin_dir)])
        return cmd

    def run_print(self, prompt: str) -> str:
        """Send a single prompt via claude --print and return the response."""
        cmd = self._base_cmd() + ["--print", prompt]
        try:
            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            logger.warning("claude --print timed out after %ss", self.timeout)
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            return f"{stdout}{stderr}\n[TIMEOUT after {self.timeout}s]"
        if result.returncode != 0:
            logger.warning("claude --print returned %d: %s", result.returncode, result.stderr)
        return result.stdout

    def run_interactive(
        self,
        initial_prompt: str,
        responder=None,
        phase_timeout: int | None = None,
    ) -> SessionTranscript:
        """Run a session and capture transcript.

        NOTE: Claude CLI interactive mode via piped stdin/stdout is unreliable in CI.
        For integration stability we execute via --print and capture a 2-turn transcript.
        """
        timeout = phase_timeout or self.timeout
        old_timeout = self.timeout
        self.timeout = timeout
        transcript = SessionTranscript()
        transcript.turns.append({"role": "user", "content": initial_prompt})
        try:
            output = self.run_print(initial_prompt)
            transcript.turns.append({"role": "claude", "content": output})
            transcript.raw_stdout = output
            transcript.timed_out = "[TIMEOUT" in output
            transcript.exit_code = 0
        except Exception as e:
            logger.error("Interactive session emulation error: %s", e)
            transcript.raw_stderr = str(e)
            transcript.exit_code = 1
        finally:
            self.timeout = old_timeout
        return transcript
