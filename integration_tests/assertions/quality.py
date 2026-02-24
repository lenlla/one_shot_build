"""Quality assertions — advisory checks that warn but don't fail tests."""

import re
from pathlib import Path

import yaml

from integration_tests.assertions.models import AssertionResult


def check_init_quality(project_dir: Path, project_name: str) -> list[AssertionResult]:
    results = []
    claude_md = project_dir / "CLAUDE.md"
    if claude_md.is_file():
        content = claude_md.read_text()
        results.append(AssertionResult(
            passed=project_name in content,
            message=f"CLAUDE.md references project name '{project_name}'",
            tier="quality",
        ))
    harnessrc = project_dir / "kyros-agent-workflow" / ".harnessrc"
    if harnessrc.is_file():
        try:
            with open(harnessrc) as f:
                config = yaml.safe_load(f) or {}
            expected_sections = ["circuit_breaker", "agent_team"]
            for section in expected_sections:
                results.append(AssertionResult(
                    passed=section in config,
                    message=f".harnessrc has '{section}' section",
                    tier="quality",
                ))
        except yaml.YAMLError:
            pass
    standards_dir = project_dir / "kyros-agent-workflow" / "docs" / "standards"
    for f in ["coding-standards.md", "definition-of-done.md", "review-criteria.md"]:
        path = standards_dir / f
        if path.is_file():
            content = path.read_text()
            results.append(AssertionResult(
                passed=len(content.strip()) > 50,
                message=f"docs/standards/{f} has substantive content",
                tier="quality",
            ))
    return results


def check_profile_data_quality(
    project_dir: Path,
    table_names: list[str],
    expected_columns: list[str],
) -> list[AssertionResult]:
    results = []
    context_dir = project_dir / "kyros-agent-workflow" / "docs" / "context"
    for table in table_names:
        profile_path = context_dir / f"data-profile-{table}.md"
        if profile_path.is_file():
            content = profile_path.read_text().lower()
            missing = [c for c in expected_columns if c.lower() not in content]
            results.append(AssertionResult(
                passed=len(missing) == 0,
                message=f"Profile mentions all columns (missing: {missing})" if missing else "Profile mentions all columns",
                tier="quality",
            ))
            has_stats = any(term in content for term in ["distribution", "null", "min", "max", "mean", "count", "unique"])
            results.append(AssertionResult(
                passed=has_stats,
                message="Profile contains distribution stats or null rates",
                tier="quality",
            ))
    notes_path = context_dir / "analyst-notes.md"
    if notes_path.is_file():
        content = notes_path.read_text().lower()
        results.append(AssertionResult(
            passed="churned" in content,
            message="Analyst notes reference 'churned' as target",
            tier="quality",
        ))
    return results


def check_define_epics_quality(epics_dir: Path) -> list[AssertionResult]:
    results = []
    yaml_files = sorted(epics_dir.glob("*.yaml"))
    for yf in yaml_files:
        try:
            with open(yf) as f:
                spec = yaml.safe_load(f) or {}
            results.append(AssertionResult(
                passed="acceptance_criteria" in spec and len(spec.get("acceptance_criteria", [])) > 0,
                message=f"{yf.name} has acceptance_criteria",
                tier="quality",
            ))
        except yaml.YAMLError:
            pass
    # Check sequential numbering
    numbered = all(re.match(r"^\d{2}-", yf.name) for yf in yaml_files)
    results.append(AssertionResult(
        passed=numbered,
        message="Epics are sequentially numbered (01-, 02-, ...)",
        tier="quality",
    ))
    return results


def check_execute_plan_quality(
    project_dir: Path,
    epics_dir: Path,
    epic_names: list[str],
) -> list[AssertionResult]:
    results = []
    for name in epic_names:
        plan_path = project_dir / "kyros-agent-workflow" / "docs" / "plans" / f"{name}-plan.md"
        if plan_path.is_file():
            content = plan_path.read_text()
            results.append(AssertionResult(
                passed="step" in content.lower(),
                message=f"Plan for {name} contains step descriptions",
                tier="quality",
            ))
    state_file = epics_dir / ".execution-state.yaml"
    if state_file.is_file():
        try:
            with open(state_file) as f:
                state = yaml.safe_load(f) or {}
            for name in epic_names:
                epic_state = state.get("epics", {}).get(name, {})
                results.append(AssertionResult(
                    passed=epic_state.get("status") == "completed",
                    message=f"Epic '{name}' status is 'completed'",
                    tier="quality",
                ))
        except yaml.YAMLError:
            pass
    return results
