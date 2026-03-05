#!/usr/bin/env python3
"""Warn/fail on sustained drift in integration lane telemetry."""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from statistics import median


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows


def _summary(rows: list[dict]) -> dict:
    durations = [float(r.get("duration_sec", 0.0)) for r in rows if r.get("outcome") != "skipped"]
    retries = [int(r.get("retry_count", 0)) for r in rows if r.get("outcome") != "skipped"]
    fails = [r for r in rows if r.get("outcome") == "fail"]
    total = len([r for r in rows if r.get("outcome") != "skipped"])
    return {
        "median_duration": median(durations) if durations else 0.0,
        "median_retry": median(retries) if retries else 0.0,
        "fail_rate": (len(fails) / total) if total else 0.0,
        "total": total,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check sustained drift in integration test telemetry")
    parser.add_argument("--current", required=True, type=Path, help="Current run JSONL")
    parser.add_argument("--history-glob", required=True, help="Glob for historical JSONL files")
    parser.add_argument("--mode", choices=["warn", "blocking"], default="warn")
    parser.add_argument("--min-history", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    current_rows = _load_jsonl(args.current)
    if not current_rows:
        print(f"[drift-check] No current metrics rows found in {args.current}; skipping.")
        return 0

    current = _summary(current_rows)
    history_paths = [Path(p) for p in sorted(glob.glob(args.history_glob)) if Path(p) != args.current]
    history_paths = history_paths[-10:]
    history_summaries = [_summary(_load_jsonl(path)) for path in history_paths]
    history_summaries = [s for s in history_summaries if s["total"] > 0]

    if len(history_summaries) < args.min_history:
        print(
            "[drift-check] Insufficient history for sustained drift check "
            f"(found {len(history_summaries)}, need {args.min_history})."
        )
        return 0

    baseline_duration = median([s["median_duration"] for s in history_summaries])
    baseline_retry = median([s["median_retry"] for s in history_summaries])
    baseline_fail_rate = median([s["fail_rate"] for s in history_summaries])

    warnings: list[str] = []
    if baseline_duration > 0 and current["median_duration"] > (baseline_duration * 1.5):
        warnings.append(
            "median duration drift: "
            f"current={current['median_duration']:.2f}s baseline={baseline_duration:.2f}s"
        )
    if current["median_retry"] > (baseline_retry + 1):
        warnings.append(
            "retry drift: "
            f"current={current['median_retry']:.2f} baseline={baseline_retry:.2f}"
        )
    if current["fail_rate"] > max(0.10, baseline_fail_rate * 2):
        warnings.append(
            "failure rate drift: "
            f"current={current['fail_rate']:.2%} baseline={baseline_fail_rate:.2%}"
        )

    if not warnings:
        print("[drift-check] No sustained drift signals detected.")
        return 0

    print("[drift-check] Drift warnings:")
    for warning in warnings:
        print(f"- {warning}")

    if args.mode == "blocking":
        print("[drift-check] Blocking mode enabled; failing on drift warnings.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
