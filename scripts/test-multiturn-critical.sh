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

python3 -m pytest \
  integration_tests/test_define_epics.py::test_define_epics_structural \
  integration_tests/test_resume_recovery.py::test_resume_after_interrupt \
  integration_tests/test_circuit_breakers.py::test_no_progress_halts \
  -q
