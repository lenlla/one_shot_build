"""Deterministic turn-by-turn Claude runner with stream-json parsing."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TurnResult:
    """Result for one Claude turn invocation."""

    prompt: str
    command: list[str]
    exit_code: int
    timed_out: bool
    log_path: Path | None
    assistant_texts: list[str]
    tool_events: list[dict[str, Any]]
    skill_names: list[str]


def run_turn(
    prompt: str,
    working_dir: Path,
    plugin_dir: Path,
    continue_session: bool = False,
    max_turns: int = 3,
    timeout: int = 300,
    log_path: Path | None = None,
) -> TurnResult:
    """Run one Claude turn and parse stream-json output."""
    command = [
        "claude",
        "-p",
        prompt,
    ]
    if continue_session:
        command.append("--continue")
    command.extend(
        [
            "--plugin-dir",
            str(plugin_dir),
            "--dangerously-skip-permissions",
            "--max-turns",
            str(max_turns),
            "--verbose",
            "--output-format",
            "stream-json",
        ]
    )

    stdout = ""
    stderr = ""
    exit_code = 1
    timed_out = False

    try:
        completed = subprocess.run(
            command,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = _to_text(exc.stdout)
        stderr = _to_text(exc.stderr)
        exit_code = 124
        timed_out = True

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(stdout + ("\n" if stdout and not stdout.endswith("\n") else "") + stderr)

    parsed = parse_stream_json_lines(stdout.splitlines())
    return TurnResult(
        prompt=prompt,
        command=command,
        exit_code=exit_code,
        timed_out=timed_out,
        log_path=log_path,
        assistant_texts=parsed["assistant_texts"],
        tool_events=parsed["tool_events"],
        skill_names=parsed["skill_names"],
    )


def parse_stream_json_lines(lines: list[str]) -> dict[str, Any]:
    """Parse stream-json output lines and return extracted artifacts."""
    assistant_texts: list[str] = []
    tool_events: list[dict[str, Any]] = []
    skill_names: list[str] = []

    for line in lines:
        payload = _safe_load_json(line)
        if not isinstance(payload, dict):
            continue

        assistant_texts.extend(_extract_assistant_text(payload))
        for tool_event in _extract_tool_use_events(payload):
            tool_events.append(tool_event)
            skill_name = _extract_skill_name(tool_event)
            if skill_name:
                skill_names.append(skill_name)

    first_skill_index = next(
        (index for index, event in enumerate(tool_events) if event.get("name") == "Skill"),
        None,
    )
    pre_skill_tool_invocations = []
    if first_skill_index is not None:
        pre_skill_tool_invocations = [
            event for event in tool_events[:first_skill_index] if event.get("name") != "Skill"
        ]

    return {
        "assistant_texts": assistant_texts,
        "tool_events": tool_events,
        "skill_names": skill_names,
        "first_skill_index": first_skill_index,
        "pre_skill_tool_invocations": pre_skill_tool_invocations,
    }


def _safe_load_json(line: str) -> dict[str, Any] | None:
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _extract_assistant_text(payload: dict[str, Any]) -> list[str]:
    texts: list[str] = []

    message = payload.get("message")
    if isinstance(message, dict):
        role = message.get("role")
        if role == "assistant":
            content = message.get("content")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text")
                        if isinstance(text, str) and text.strip():
                            texts.append(text)

    if payload.get("type") in {"assistant", "assistant_message"}:
        text = payload.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text)

    return texts


def _extract_tool_use_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    if payload.get("type") == "tool_use" and isinstance(payload.get("name"), str):
        events.append(payload)

    message = payload.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "tool_use" and isinstance(item.get("name"), str):
                    events.append(item)

    return events


def _extract_skill_name(tool_event: dict[str, Any]) -> str | None:
    if tool_event.get("name") != "Skill":
        return None

    tool_input = tool_event.get("input")
    if not isinstance(tool_input, dict):
        return None

    candidate = None
    for key in ("skill", "name", "command"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            candidate = value.strip()
            break

    if not candidate:
        return None

    candidate = candidate.lstrip("$")
    if "/" in candidate:
        candidate = candidate.split("/")[-1]
    return candidate or None
