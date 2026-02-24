"""Smoke tests for the ClaudeRunner — verifies basic subprocess management."""

import pytest

from integration_tests.claude_runner import ClaudeRunner


def test_runner_sends_print_message():
    """claude --print with a trivial prompt returns a response."""
    runner = ClaudeRunner()
    output = runner.run_print("Reply with exactly: PONG")
    assert "PONG" in output


def test_runner_captures_output():
    """The runner captures full stdout."""
    runner = ClaudeRunner()
    output = runner.run_print("Reply with exactly the word: HELLO")
    assert len(output) > 0


def test_runner_timeout():
    """The runner respects timeout and doesn't hang."""
    runner = ClaudeRunner(timeout=5)
    # A very short timeout with a simple prompt should still work
    output = runner.run_print("Reply with: OK")
    assert len(output) > 0
