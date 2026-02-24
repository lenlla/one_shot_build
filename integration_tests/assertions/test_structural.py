import tempfile
from pathlib import Path

import yaml

from integration_tests.assertions.structural import check_init, check_profile_data, check_define_epics, check_execute_plan


def test_check_init_passes_on_valid_project(tmp_path):
    """A properly initialized project passes all structural checks."""
    _create_valid_init(tmp_path)
    results = check_init(tmp_path)
    failures = [r for r in results if not r.passed]
    assert len(failures) == 0, f"Unexpected failures: {[r.message for r in failures]}"


def test_check_init_fails_on_empty_dir(tmp_path):
    """An empty directory fails all structural checks."""
    results = check_init(tmp_path)
    failures = [r for r in results if not r.passed]
    assert len(failures) > 0


def test_check_profile_data_passes_on_valid(tmp_path):
    """A project with valid data profiles passes structural checks."""
    _create_valid_init(tmp_path)
    _create_valid_profile(tmp_path)
    results = check_profile_data(tmp_path, table_names=["customers"])
    failures = [r for r in results if not r.passed]
    assert len(failures) == 0, f"Unexpected failures: {[r.message for r in failures]}"


def test_check_profile_data_fails_without_profile(tmp_path):
    """Missing profile files fail structural checks."""
    _create_valid_init(tmp_path)
    results = check_profile_data(tmp_path, table_names=["customers"])
    failures = [r for r in results if not r.passed]
    assert len(failures) > 0


def test_check_define_epics_passes_on_valid(tmp_path):
    """Valid epic specs pass structural checks."""
    _create_valid_init(tmp_path)
    epics_dir = tmp_path / "epics" / "v1"
    epics_dir.mkdir(parents=True)
    _create_valid_epics(epics_dir)
    results = check_define_epics(tmp_path, epics_dir)
    failures = [r for r in results if not r.passed]
    assert len(failures) == 0, f"Unexpected failures: {[r.message for r in failures]}"


def test_check_define_epics_fails_on_empty_dir(tmp_path):
    """Empty epics directory fails structural checks."""
    epics_dir = tmp_path / "epics" / "v1"
    epics_dir.mkdir(parents=True)
    results = check_define_epics(tmp_path, epics_dir)
    failures = [r for r in results if not r.passed]
    assert len(failures) > 0


def _create_valid_init(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("<!-- begin:one-shot-build -->\ntest\n<!-- end:one-shot-build -->")
    harness = tmp_path / "kyros-agent-workflow"
    harness.mkdir(exist_ok=True)
    (harness / ".harnessrc").write_text("circuit_breaker:\n  no_progress_threshold: 3\n")
    for subdir in ["docs/context", "docs/standards", "docs/solutions", "docs/plans", "docs/epics",
                    "config", "src/utils", "tests", "scripts"]:
        (harness / subdir).mkdir(parents=True, exist_ok=True)
    for f in ["coding-standards.md", "definition-of-done.md", "review-criteria.md"]:
        (harness / "docs" / "standards" / f).write_text(f"# {f}\n\nContent here.\n")


def _create_valid_profile(tmp_path: Path):
    context_dir = tmp_path / "kyros-agent-workflow" / "docs" / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    (context_dir / "data-profile-customers.md").write_text(
        "# Data Profile: customers\n\n| Column | Type |\n|---|---|\n| customer_id | int |\n"
    )
    (context_dir / "analyst-notes.md").write_text("# Analyst Notes\n\nTarget: churned\n")


def _create_valid_epics(epics_dir: Path):
    for i, name in enumerate(["data-loading", "model-training"], start=1):
        spec = {
            "name": name,
            "description": f"Epic for {name}",
            "acceptance_criteria": [f"Criterion for {name}"],
            "dependencies": [],
            "estimated_steps": 3,
        }
        with open(epics_dir / f"{i:02d}-{name}.yaml", "w") as f:
            yaml.dump(spec, f)
