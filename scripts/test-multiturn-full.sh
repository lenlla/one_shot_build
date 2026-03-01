#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v claude >/dev/null 2>&1; then
  echo "ERROR: claude CLI is required for multi-turn tests"
  exit 1
fi

python3 -m pip install --upgrade pip
python3 -m pip install -r integration_tests/requirements.txt

METRICS_DIR="${METRICS_DIR:-.integration-metrics}"
mkdir -p "$METRICS_DIR/history"
JUNIT_XML="$METRICS_DIR/full-junit.xml"
JSONL="$METRICS_DIR/full-metrics.jsonl"

set +e
python3 -m pytest integration_tests --junitxml="$JUNIT_XML" -q
PYTEST_EXIT=$?
set -e

python3 -m integration_tests.metrics --junit "$JUNIT_XML" --jsonl "$JSONL" --lane full
cp "$JSONL" "$METRICS_DIR/history/full-$(date +%Y%m%d-%H%M%S).jsonl"
python3 scripts/check-flake-drift.py \
  --current "$JSONL" \
  --history-glob "$METRICS_DIR/history/full-*.jsonl" \
  --mode warn

exit "$PYTEST_EXIT"
