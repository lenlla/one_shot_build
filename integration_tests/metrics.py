"""Helpers for emitting lane telemetry from pytest JUnit XML."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def junit_to_jsonl(junit_path: Path, jsonl_path: Path, lane: str) -> int:
    if not junit_path.exists():
        raise FileNotFoundError(f"JUnit XML not found: {junit_path}")

    tree = ET.parse(junit_path)
    root = tree.getroot()
    testcases = root.findall(".//testcase")

    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in testcases:
        classname = case.attrib.get("classname", "")
        name = case.attrib.get("name", "")
        test_name = f"{classname}::{name}" if classname else name
        duration = float(case.attrib.get("time", "0") or 0.0)

        outcome = "pass"
        failure_reason = ""
        if case.find("failure") is not None:
            outcome = "fail"
            failure_reason = _classify_failure(case.find("failure").attrib.get("message", ""))
        elif case.find("error") is not None:
            outcome = "fail"
            failure_reason = _classify_failure(case.find("error").attrib.get("message", ""))
        elif case.find("skipped") is not None:
            outcome = "skipped"
            failure_reason = "skipped"

        rows.append(
            {
                "lane": lane,
                "test_name": test_name,
                "duration_sec": duration,
                "retry_count": 0,
                "outcome": outcome,
                "failure_reason": failure_reason,
            }
        )

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True))
            handle.write("\n")
    return len(rows)


def _classify_failure(message: str) -> str:
    normalized = (message or "").lower()
    if re.search(r"\btimeout\b|timed out|exit code 124", normalized):
        return "timeout"
    if "assert" in normalized:
        return "assertion"
    return "error"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit JSONL telemetry from pytest JUnit XML")
    parser.add_argument("--junit", required=True, type=Path, help="Path to pytest junit xml file")
    parser.add_argument("--jsonl", required=True, type=Path, help="Path to output jsonl file")
    parser.add_argument("--lane", required=True, help="Lane name (critical/full)")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    count = junit_to_jsonl(args.junit, args.jsonl, args.lane)
    print(f"Wrote {count} test metrics rows to {args.jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
