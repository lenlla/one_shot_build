#!/usr/bin/env bash
# dashboard/serve.sh
# Launches a local HTTP server for the Kanban dashboard.
# Serves both the dashboard files AND the project's state file.
# Usage: serve.sh [project-root-or-build-dir] [port]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PROJECT_ROOT="${1:-$(pwd)}"
PORT="${2:-8080}"

# Create a temp directory with symlinks so the server can access both
SERVE_DIR=$(mktemp -d)
ln -s "$SCRIPT_DIR"/* "$SERVE_DIR/" 2>/dev/null || true

# Check if the argument itself contains .execution-state.yaml
if [[ -f "$PROJECT_ROOT/.execution-state.yaml" ]]; then
    ln -s "$PROJECT_ROOT/.execution-state.yaml" "$SERVE_DIR/execution-state.yaml" 2>/dev/null || true
    echo "State file: $PROJECT_ROOT/.execution-state.yaml"
else
    # Search recursively for the first execution state file
    find "$PROJECT_ROOT" -name ".execution-state.yaml" -not -path "*/.git/*" 2>/dev/null | while read -r state_file; do
        ln -s "$state_file" "$SERVE_DIR/execution-state.yaml" 2>/dev/null || true
        echo "State file: $state_file"
        break
    done
fi

if [[ ! -L "$SERVE_DIR/execution-state.yaml" ]]; then
    echo "WARNING: No .execution-state.yaml found under $PROJECT_ROOT"
fi

# Cleanup on exit
trap 'rm -rf "$SERVE_DIR"' EXIT

echo "Kanban Dashboard: http://localhost:${PORT}"
echo "Project root: $PROJECT_ROOT"
echo "Press Ctrl+C to stop."

# Serve with Python's built-in HTTP server
cd "$SERVE_DIR"
python3 -m http.server "$PORT" --bind 127.0.0.1
