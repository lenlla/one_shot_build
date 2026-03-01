"""Fast deterministic checks for execute-plan orchestration artifacts.

This suite validates artifact contracts without running a full multi-turn execute-plan flow.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from integration_tests.assertions.structural import check_execute_plan


def test_execute_plan_artifacts_pass_on_valid_state_and_git_contracts(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _create_state_file(tmp_path)
    _create_epic_branches_and_tags(tmp_path)

    epics_dir = tmp_path / "epics" / "v1"
    epics_dir.mkdir(parents=True, exist_ok=True)
    result = check_execute_plan(
        tmp_path,
        epics_dir,
        epic_names=["data-loading", "model-training"],
    )
    failures = [r for r in result if not r.passed]
    assert not failures, f"Unexpected artifact failures: {[f.message for f in failures]}"

    state_path = tmp_path / "kyros-agent-workflow" / "builds" / "v1" / "epic-specs" / ".execution-state.yaml"
    state = yaml.safe_load(state_path.read_text())
    assert state["mode"] == "autonomous"
    assert isinstance(state["epics"], list) and len(state["epics"]) == 2
    assert {epic["name"] for epic in state["epics"]} == {"data-loading", "model-training"}


def test_execute_plan_artifacts_fail_when_branch_and_tag_missing(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    _create_state_file(tmp_path)
    # Intentionally create only one epic's branch/tag to verify strict contract failure.
    _create_epic_branches_and_tags(tmp_path, include_model_training=False)

    epics_dir = tmp_path / "epics" / "v1"
    epics_dir.mkdir(parents=True, exist_ok=True)
    result = check_execute_plan(
        tmp_path,
        epics_dir,
        epic_names=["data-loading", "model-training"],
    )
    failures = [r.message for r in result if not r.passed]
    assert any("Branch epic/model-training exists" == msg for msg in failures)
    assert any("Tag tdd-baseline-model-training exists" == msg for msg in failures)


def _init_git_repo(project_dir: Path) -> None:
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
    (project_dir / "README.md").write_text("# test repo\n")
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=project_dir, check=True, capture_output=True)


def _create_state_file(project_dir: Path) -> None:
    state_path = project_dir / "kyros-agent-workflow" / "builds" / "v1" / "epic-specs" / ".execution-state.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "build_dir": "kyros-agent-workflow/builds/v1",
        "mode": "autonomous",
        "started_at": "2026-03-01T00:00:00Z",
        "epics": [
            {"name": "data-loading", "spec": "01-data-loading.yaml", "status": "complete", "steps": []},
            {"name": "model-training", "spec": "02-model-training.yaml", "status": "in_progress", "steps": []},
        ],
    }
    state_path.write_text(yaml.safe_dump(state, sort_keys=False))


def _create_epic_branches_and_tags(project_dir: Path, include_model_training: bool = True) -> None:
    subprocess.run(["git", "branch", "epic/data-loading"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(["git", "tag", "tdd-baseline-data-loading"], cwd=project_dir, check=True, capture_output=True)
    if include_model_training:
        subprocess.run(["git", "branch", "epic/model-training"], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(["git", "tag", "tdd-baseline-model-training"], cwd=project_dir, check=True, capture_output=True)
