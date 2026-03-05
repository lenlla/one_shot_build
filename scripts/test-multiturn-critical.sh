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
JUNIT_XML="$METRICS_DIR/critical-junit.xml"
JSONL="$METRICS_DIR/critical-metrics.jsonl"
DRIFT_MODE="${DRIFT_MODE:-warn}"
DRIFT_MIN_HISTORY="${DRIFT_MIN_HISTORY:-3}"

set +e
python3 -m pytest \
  integration_tests/test_define_epics.py::test_define_epics_structural \
  integration_tests/test_resume_recovery.py::test_resume_after_interrupt \
  integration_tests/test_circuit_breakers.py::test_no_progress_halts \
  --junitxml="$JUNIT_XML" \
  -q
PYTEST_EXIT=$?
set -e

python3 -m integration_tests.metrics --junit "$JUNIT_XML" --jsonl "$JSONL" --lane critical
cp "$JSONL" "$METRICS_DIR/history/critical-$(date +%Y%m%d-%H%M%S).jsonl"
python3 scripts/check-flake-drift.py \
  --current "$JSONL" \
  --history-glob "$METRICS_DIR/history/critical-*.jsonl" \
  --mode "$DRIFT_MODE" \
  --min-history "$DRIFT_MIN_HISTORY"

exit "$PYTEST_EXIT"
