"""Unit tests for multi-turn stream-json parsing helpers."""

from integration_tests.turn_runner import parse_stream_json_lines


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
