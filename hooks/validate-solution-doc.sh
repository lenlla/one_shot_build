#!/usr/bin/env bash
# hooks/validate-solution-doc.sh
# Validates a solution document's YAML frontmatter against the schema.
# Also checks for contradictions with existing docs (same component+problem_type+root_cause).
# Usage: validate-solution-doc.sh <doc-path> [schema-path] [solutions-dir]
# Exit 0 = PASS (may include OVERLAP warnings), Exit 1 = FAIL

set -euo pipefail

DOC_PATH="${1:?Usage: validate-solution-doc.sh <doc-path> [schema-path] [solutions-dir]}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
SCHEMA_PATH="${2:-${SCRIPT_DIR}/../lib/solution-schema.yaml}"
SOLUTIONS_DIR="${3:-}"  # Optional: path to docs/solutions/ for contradiction detection

if [[ ! -f "$DOC_PATH" ]]; then
    echo "FAIL: File not found: $DOC_PATH"
    exit 1
fi

if ! command -v yq &>/dev/null; then
    echo "FAIL: yq is required for solution doc validation"
    exit 1
fi

failures=()
warnings=()

# Extract frontmatter (between --- markers)
frontmatter=$(sed -n '/^---$/,/^---$/p' "$DOC_PATH" | sed '1d;$d')
if [[ -z "$frontmatter" ]]; then
    echo "FAIL: No YAML frontmatter found in $DOC_PATH"
    exit 1
fi

# Write frontmatter to temp file for yq parsing
tmp_fm=$(mktemp)
echo "$frontmatter" > "$tmp_fm"

# Check required fields
required_fields=("title" "date" "problem_type" "component" "severity" "root_cause" "resolution_type")
for field in "${required_fields[@]}"; do
    val=$(yq eval ".${field}" "$tmp_fm" 2>/dev/null)
    if [[ -z "$val" || "$val" == "null" ]]; then
        failures+=("Required field missing: ${field}")
    fi
done

# Validate enum fields against schema
enum_fields=("problem_type" "component" "severity" "root_cause" "resolution_type" "status")
for field in "${enum_fields[@]}"; do
    val=$(yq eval ".${field}" "$tmp_fm" 2>/dev/null)
    if [[ -n "$val" && "$val" != "null" ]]; then
        match=$(yq eval ".${field}[] | select(. == \"${val}\")" "$SCHEMA_PATH" 2>/dev/null)
        if [[ -z "$match" ]]; then
            failures+=("Invalid ${field}: '${val}' — see lib/solution-schema.yaml for valid values")
        fi
    fi
done

# Validate applies_to.scope
scope=$(yq eval ".applies_to.scope" "$tmp_fm" 2>/dev/null)
if [[ -n "$scope" && "$scope" != "null" ]]; then
    match=$(yq eval ".scope[] | select(. == \"${scope}\")" "$SCHEMA_PATH" 2>/dev/null)
    if [[ -z "$match" ]]; then
        failures+=("Invalid applies_to.scope: '${scope}' — must be 'universal' or 'conditional'")
    fi
fi

# --- Contradiction detection ---
# Check for existing active docs with the same component+problem_type+root_cause
if [[ -n "$SOLUTIONS_DIR" && -d "$SOLUTIONS_DIR" ]]; then
    new_component=$(yq eval ".component" "$tmp_fm" 2>/dev/null)
    new_problem=$(yq eval ".problem_type" "$tmp_fm" 2>/dev/null)
    new_root=$(yq eval ".root_cause" "$tmp_fm" 2>/dev/null)

    if [[ -n "$new_component" && -n "$new_problem" && -n "$new_root" ]]; then
        # Search existing docs for matching combination
        while IFS= read -r existing_doc; do
            [[ "$existing_doc" == "$DOC_PATH" ]] && continue
            [[ "$existing_doc" == *"_archived"* ]] && continue

            ex_fm=$(sed -n '/^---$/,/^---$/p' "$existing_doc" | sed '1d;$d')
            tmp_ex=$(mktemp)
            echo "$ex_fm" > "$tmp_ex"

            ex_component=$(yq eval ".component" "$tmp_ex" 2>/dev/null)
            ex_problem=$(yq eval ".problem_type" "$tmp_ex" 2>/dev/null)
            ex_root=$(yq eval ".root_cause" "$tmp_ex" 2>/dev/null)
            ex_status=$(yq eval ".status" "$tmp_ex" 2>/dev/null)
            ex_title=$(yq eval ".title" "$tmp_ex" 2>/dev/null)

            rm -f "$tmp_ex"

            if [[ "$ex_component" == "$new_component" && \
                  "$ex_problem" == "$new_problem" && \
                  "$ex_root" == "$new_root" && \
                  "$ex_status" == "active" ]]; then
                warnings+=("OVERLAP: Existing active doc covers same component+problem_type+root_cause: ${existing_doc} (\"${ex_title}\"). Consider marking it as superseded.")
            fi
        done < <(find "$SOLUTIONS_DIR" -name "*.md" -not -path "*/_archived/*" 2>/dev/null)
    fi
fi

rm -f "$tmp_fm"

# Report
if [[ ${#failures[@]} -gt 0 ]]; then
    echo "FAIL: Solution doc validation failed: $(basename "$DOC_PATH")"
    echo ""
    for fail in "${failures[@]}"; do
        echo "  - $fail"
    done
    exit 1
fi

# Warnings (non-blocking)
for warn in "${warnings[@]}"; do
    echo "  $warn"
done

echo "PASS: Solution doc validates against schema: $(basename "$DOC_PATH")"
exit 0
