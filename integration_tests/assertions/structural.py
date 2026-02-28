"""Structural assertions — hard gates that must pass for a phase to be considered successful."""

from pathlib import Path

import yaml

from integration_tests.assertions.models import AssertionResult


def check_init(project_dir: Path) -> list[AssertionResult]:
    results = []
    results.append(_file_exists(project_dir / "CLAUDE.md", "CLAUDE.md exists at project root"))
    results.append(_dir_exists(project_dir / "kyros-agent-workflow", "kyros-agent-workflow/ directory exists"))
    harnessrc = project_dir / "kyros-agent-workflow" / ".harnessrc"
    results.append(_file_exists(harnessrc, ".harnessrc exists"))
    results.append(_yaml_parses(harnessrc, ".harnessrc parses as valid YAML"))
    for f in ["coding-standards.md", "definition-of-done.md", "review-criteria.md"]:
        results.append(_file_exists(
            project_dir / "kyros-agent-workflow" / "docs" / "standards" / f,
            f"docs/standards/{f} exists",
        ))
    results.append(_dir_exists(
        project_dir / "kyros-agent-workflow" / "docs" / "solutions",
        "docs/solutions/ directory exists",
    ))
    return results


def check_profile_data(project_dir: Path, table_names: list[str]) -> list[AssertionResult]:
    results = []
    context_dir = project_dir / "kyros-agent-workflow" / "docs" / "context"
    for table in table_names:
        profile_path = context_dir / f"data-profile-{table}.md"
        results.append(_file_exists(profile_path, f"data-profile-{table}.md exists"))
        results.append(_file_not_empty(profile_path, f"data-profile-{table}.md is non-empty"))
    notes_path = context_dir / "analyst-notes.md"
    if notes_path.exists():
        results.append(_file_not_empty(notes_path, "analyst-notes.md is non-empty"))
    return results


def check_define_epics(project_dir: Path, epics_dir: Path) -> list[AssertionResult]:
    results = []
    results.append(_dir_exists(epics_dir, f"Epics directory {epics_dir.name} exists"))
    yaml_files = sorted(epics_dir.glob("*.yaml"))
    results.append(AssertionResult(
        passed=len(yaml_files) >= 2,
        message=f"At least 2 epic YAML files (found {len(yaml_files)})",
        tier="structural",
    ))
    for yf in yaml_files:
        results.append(_yaml_parses(yf, f"{yf.name} parses as valid YAML"))
    return results


def check_execute_plan(project_dir: Path, epics_dir: Path, epic_names: list[str]) -> list[AssertionResult]:
    results = []
    state_candidates = [
        epics_dir / ".execution-state.yaml",
        project_dir / "kyros-agent-workflow" / "builds" / "v1" / ".execution-state.yaml",
    ]
    state_file = next((p for p in state_candidates if p.is_file()), state_candidates[0])
    results.append(_file_exists(state_file, ".execution-state.yaml exists"))
    results.append(_yaml_parses(state_file, ".execution-state.yaml parses as valid YAML"))
    for name in epic_names:
        results.append(_git_branch_exists(project_dir, f"epic/{name}", f"Branch epic/{name} exists"))
        results.append(_git_tag_exists(project_dir, f"tdd-baseline-{name}", f"Tag tdd-baseline-{name} exists"))
    return results


def _file_exists(path: Path, message: str) -> AssertionResult:
    return AssertionResult(passed=path.is_file(), message=message, tier="structural")


def _dir_exists(path: Path, message: str) -> AssertionResult:
    return AssertionResult(passed=path.is_dir(), message=message, tier="structural")


def _file_not_empty(path: Path, message: str) -> AssertionResult:
    return AssertionResult(
        passed=path.is_file() and path.stat().st_size > 0,
        message=message,
        tier="structural",
    )


def _yaml_parses(path: Path, message: str) -> AssertionResult:
    if not path.is_file():
        return AssertionResult(passed=False, message=f"{message} (file not found)", tier="structural")
    try:
        with open(path) as f:
            yaml.safe_load(f)
        return AssertionResult(passed=True, message=message, tier="structural")
    except yaml.YAMLError:
        return AssertionResult(passed=False, message=f"{message} (invalid YAML)", tier="structural")


def _git_branch_exists(project_dir: Path, branch: str, message: str) -> AssertionResult:
    import subprocess
    result = subprocess.run(
        ["git", "branch", "--list", branch],
        cwd=project_dir, capture_output=True, text=True,
    )
    return AssertionResult(passed=branch in result.stdout, message=message, tier="structural")


def _git_tag_exists(project_dir: Path, tag: str, message: str) -> AssertionResult:
    import subprocess
    result = subprocess.run(
        ["git", "tag", "--list", tag],
        cwd=project_dir, capture_output=True, text=True,
    )
    return AssertionResult(passed=tag in result.stdout, message=message, tier="structural")
