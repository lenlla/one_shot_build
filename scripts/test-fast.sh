#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

npm ci
./node_modules/.bin/bats tests/*.bats

python3 -m pip install --upgrade pip
python3 -m pip install -r integration_tests/requirements.txt
python3 -m pytest integration_tests/assertions/test_structural.py integration_tests/assertions/test_quality.py -q
