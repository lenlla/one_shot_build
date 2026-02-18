#!/usr/bin/env bash
# dashboard/serve.sh
# Launches a local HTTP server for the Kanban dashboard.
# Serves both the dashboard files AND the project's state file.
# Usage: serve.sh [project-root] [port]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PROJECT_ROOT="${1:-$(pwd)}"
PORT="${2:-8080}"

# Create a temp directory with symlinks so the server can access both
SERVE_DIR=$(mktemp -d)
ln -s "$SCRIPT_DIR"/* "$SERVE_DIR/" 2>/dev/null || true
# Symlink any execution state files found in the project
find "$PROJECT_ROOT" -name ".execution-state.yaml" -not -path "*/.git/*" 2>/dev/null | while read -r state_file; do
    ln -s "$state_file" "$SERVE_DIR/execution-state.yaml" 2>/dev/null || true
    break  # Use the first one found
done

# Cleanup on exit
trap "rm -rf $SERVE_DIR" EXIT

echo "Kanban Dashboard: http://localhost:${PORT}"
echo "Project root: $PROJECT_ROOT"
echo "Press Ctrl+C to stop."

# Serve with Python's built-in HTTP server
cd "$SERVE_DIR"
python3 -m http.server "$PORT" --bind 127.0.0.1
