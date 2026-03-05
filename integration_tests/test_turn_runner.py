"""Unit tests for multi-turn stream-json parsing helpers."""

from pathlib import Path
from subprocess import TimeoutExpired

from integration_tests.turn_runner import parse_stream_json_lines
from integration_tests.turn_runner import run_turn


def test_parse_stream_json_detects_skill_invocation():
    lines = [
        '{"type":"message","message":{"role":"assistant","content":[{"type":"text","text":"Starting."}]}}',
        '{"type":"tool_use","id":"1","name":"Skill","input":{"skill":"executing-plans"}}',
        '{"type":"tool_use","id":"2","name":"TodoWrite","input":{"content":"Task list"}}',
    ]

    parsed = parse_stream_json_lines(lines)

    assert parsed["assistant_texts"] == ["Starting."]
    assert parsed["skill_names"] == ["executing-plans"]
    assert [event.get("name") for event in parsed["tool_events"]] == ["Skill", "TodoWrite"]


def test_parse_stream_json_reports_pre_skill_tools():
    lines = [
        '{"type":"tool_use","id":"1","name":"TodoWrite","input":{"content":"premature"}}',
        '{"type":"tool_use","id":"2","name":"Skill","input":{"skill":"executing-plans"}}',
        '{"type":"tool_use","id":"3","name":"Task","input":{"description":"execute"}}',
    ]

    parsed = parse_stream_json_lines(lines)

    assert parsed["first_skill_index"] == 1
    assert [event.get("name") for event in parsed["pre_skill_tool_invocations"]] == ["TodoWrite"]


def test_parse_stream_json_ignores_malformed_lines():
    lines = [
        "not-json",
        '{"type":"message","message":{"role":"assistant","content":[{"type":"text","text":"Still works."}]}}',
        '{"type":"tool_use","name":"Skill","input":{"command":"$executing-plans"}}',
        '{"type":"tool_use","name":"Task","input":"oops"',
    ]

    parsed = parse_stream_json_lines(lines)

    assert parsed["assistant_texts"] == ["Still works."]
    assert parsed["skill_names"] == ["executing-plans"]
    assert [event.get("name") for event in parsed["tool_events"]] == ["Skill"]


def test_run_turn_uses_verbose_with_stream_json(monkeypatch, tmp_path):
    class _Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    captured = {}

    def _fake_run(cmd, cwd, capture_output, text, timeout):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return _Completed()

    monkeypatch.setattr("integration_tests.turn_runner.subprocess.run", _fake_run)

    run_turn(
        prompt="hello",
        working_dir=tmp_path,
        plugin_dir=Path("/tmp/plugin"),
    )

    assert "--output-format" in captured["cmd"]
    assert "stream-json" in captured["cmd"]
    assert "--verbose" in captured["cmd"]


def test_run_turn_handles_timeout_with_bytes_output(monkeypatch, tmp_path):
    def _fake_run(cmd, cwd, capture_output, text, timeout):
        raise TimeoutExpired(
            cmd=cmd,
            timeout=timeout,
            output=b"partial-json-line",
            stderr=b"timed out",
        )

    monkeypatch.setattr("integration_tests.turn_runner.subprocess.run", _fake_run)
    log_path = tmp_path / "timeout.log"

    result = run_turn(
        prompt="hello",
        working_dir=tmp_path,
        plugin_dir=Path("/tmp/plugin"),
        timeout=1,
        log_path=log_path,
    )

    assert result.timed_out is True
    assert result.exit_code == 124
    assert log_path.exists()
