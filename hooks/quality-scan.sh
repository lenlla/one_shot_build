#!/usr/bin/env bash
# hooks/quality-scan.sh
# Background quality/deviation scan
# Checks for: coding standard violations, unused imports, hand-rolled helpers,
# TODO comments, debug prints, type annotation gaps

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${PLUGIN_ROOT}/lib/state.sh"

echo "=== Quality Scan ==="
echo ""

findings=0

# --- Check 1: TODO/FIXME comments ---
echo "Checking for TODO/FIXME comments..."
todos=$(grep -rn "TODO\|FIXME\|HACK\|XXX" "${HARNESS_DIR}/src/" 2>/dev/null || true)
if [[ -n "$todos" ]]; then
    echo "  FOUND: TODO/FIXME comments"
    echo "$todos" | head -20 | sed 's/^/    /'
    findings=$((findings + 1))
else
    echo "  OK: No TODO/FIXME comments"
fi
echo ""

# --- Check 2: Debug print statements ---
echo "Checking for debug print() statements..."
prints=$(grep -rn "print(" "${HARNESS_DIR}/src/" --include="*.py" 2>/dev/null | grep -v "# noqa" || true)
if [[ -n "$prints" ]]; then
    echo "  FOUND: Debug print() statements"
    echo "$prints" | head -20 | sed 's/^/    /'
    findings=$((findings + 1))
else
    echo "  OK: No debug prints"
fi
echo ""

# --- Check 3: Unused imports (basic check) ---
echo "Checking for potential unused imports..."
if command -v ruff &>/dev/null; then
    unused=$(ruff check "${HARNESS_DIR}/src/" --select F401 2>/dev/null || true)
    if [[ -n "$unused" ]]; then
        echo "  FOUND: Unused imports"
        echo "$unused" | head -20 | sed 's/^/    /'
        findings=$((findings + 1))
    else
        echo "  OK: No unused imports detected"
    fi
else
    echo "  SKIP: ruff not installed (install for unused import detection)"
fi
echo ""

# --- Check 4: Missing type hints on public functions ---
echo "Checking for functions missing type hints..."
missing_hints=$(grep -rn "def [a-zA-Z_][a-zA-Z0-9_]*(.*)[^>]*:$" "${HARNESS_DIR}/src/" --include="*.py" 2>/dev/null | grep -v "__" | grep -v "-> " || true)
if [[ -n "$missing_hints" ]]; then
    echo "  FOUND: Functions missing return type hints"
    echo "$missing_hints" | head -20 | sed 's/^/    /'
    findings=$((findings + 1))
else
    echo "  OK: All public functions have return type hints"
fi
echo ""

# --- Summary ---
echo "=== Scan Complete ==="
if [[ $findings -eq 0 ]]; then
    echo "No issues found."
else
    echo "$findings issue category(ies) found. Review above for details."
fi
