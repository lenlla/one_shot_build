"""Wrapper around the claude CLI for integration testing.

Provides two modes:
- run_print(): Non-interactive, sends a single prompt via --print flag
- run_interactive(): Interactive, streams stdin/stdout for multi-turn sessions
"""

import json
import logging
import subprocess
import threading
import time
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

    def run_print(self, prompt: str) -> str:
        """Send a single prompt via claude --print and return the response."""
        cmd = ["claude", "--print", prompt]
        if self.plugin_dir:
            cmd.extend(["--plugin", str(self.plugin_dir)])
        result = subprocess.run(
            cmd,
            cwd=self.working_dir,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if result.returncode != 0:
            logger.warning("claude --print returned %d: %s", result.returncode, result.stderr)
        return result.stdout

    def run_interactive(
        self,
        initial_prompt: str,
        responder=None,
        phase_timeout: int | None = None,
    ) -> SessionTranscript:
        """Run an interactive claude session with optional live responder.

        Args:
            initial_prompt: The first message to send.
            responder: Optional callable(turn_text) -> str|None that generates
                       responses to unexpected questions. Return None to skip.
            phase_timeout: Override instance timeout for this session.
        """
        timeout = phase_timeout or self.timeout
        transcript = SessionTranscript()

        cmd = ["claude"]
        if self.plugin_dir:
            cmd.extend(["--plugin", str(self.plugin_dir)])

        proc = subprocess.Popen(
            cmd,
            cwd=self.working_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout_lines = []
        stderr_lines = []

        def read_stderr():
            for line in proc.stderr:
                stderr_lines.append(line)

        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()

        try:
            # Send initial prompt
            proc.stdin.write(initial_prompt + "\n")
            proc.stdin.flush()
            transcript.turns.append({"role": "user", "content": initial_prompt})

            current_turn = []
            last_output_time = time.time()
            response_count = 0
            max_responses = 20

            while True:
                # Check timeout
                if time.time() - last_output_time > timeout:
                    transcript.timed_out = True
                    break

                # Try to read a line (non-blocking via timeout)
                try:
                    proc.stdout.flush()
                    line = proc.stdout.readline()
                    if not line:
                        # Process exited
                        break
                    current_turn.append(line)
                    last_output_time = time.time()
                except Exception:
                    break

                # Check if Claude is waiting for input (5s silence)
                if responder and time.time() - last_output_time > 5:
                    turn_text = "".join(current_turn)
                    if turn_text.strip():
                        transcript.turns.append({"role": "claude", "content": turn_text})
                        response = responder(turn_text)
                        if response and response_count < max_responses:
                            proc.stdin.write(response + "\n")
                            proc.stdin.flush()
                            transcript.turns.append({"role": "user", "content": response})
                            response_count += 1
                            current_turn = []

        except Exception as e:
            logger.error("Interactive session error: %s", e)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()

            transcript.raw_stdout = "".join(stdout_lines) if stdout_lines else ""
            transcript.raw_stderr = "".join(stderr_lines)
            transcript.exit_code = proc.returncode

            # Capture any remaining turn
            remaining = "".join(current_turn)
            if remaining.strip():
                transcript.turns.append({"role": "claude", "content": remaining})

        return transcript
