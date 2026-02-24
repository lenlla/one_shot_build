from pathlib import Path

from integration_tests.assertions.quality import check_init_quality, check_profile_data_quality, check_define_epics_quality


EXPECTED_COLUMNS = ["customer_id", "age", "tenure_months", "monthly_spend", "support_tickets", "churned"]


def test_init_quality_passes(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("## One-Shot Build — integration-test-churn\n")
    harnessrc = tmp_path / "kyros-agent-workflow" / ".harnessrc"
    harnessrc.parent.mkdir(parents=True)
    harnessrc.write_text("circuit_breaker:\n  no_progress_threshold: 3\nagent_team:\n  developer_model: sonnet\n")
    standards = tmp_path / "kyros-agent-workflow" / "docs" / "standards"
    standards.mkdir(parents=True)
    for f in ["coding-standards.md", "definition-of-done.md", "review-criteria.md"]:
        (standards / f).write_text(f"# {f}\n\nSubstantive content here with enough detail to pass the quality threshold check.\n")
    results = check_init_quality(tmp_path, project_name="integration-test-churn")
    failures = [r for r in results if not r.passed]
    assert len(failures) == 0, f"Unexpected failures: {[r.message for r in failures]}"


def test_profile_quality_passes(tmp_path):
    context = tmp_path / "kyros-agent-workflow" / "docs" / "context"
    context.mkdir(parents=True)
    profile_content = "# Data Profile: customers\n\nColumn count: 6, null rate: 0%\n\n" + "\n".join(f"- {c}" for c in EXPECTED_COLUMNS)
    (context / "data-profile-customers.md").write_text(profile_content)
    (context / "analyst-notes.md").write_text("Target variable: churned\n")
    results = check_profile_data_quality(tmp_path, table_names=["customers"], expected_columns=EXPECTED_COLUMNS)
    failures = [r for r in results if not r.passed]
    assert len(failures) == 0, f"Unexpected failures: {[r.message for r in failures]}"


def test_profile_quality_warns_on_missing_columns(tmp_path):
    context = tmp_path / "kyros-agent-workflow" / "docs" / "context"
    context.mkdir(parents=True)
    (context / "data-profile-customers.md").write_text("# Data Profile\n\nSome content.\n")
    (context / "analyst-notes.md").write_text("Notes here.\n")
    results = check_profile_data_quality(tmp_path, table_names=["customers"], expected_columns=EXPECTED_COLUMNS)
    warnings = [r for r in results if not r.passed]
    assert len(warnings) > 0


def test_epics_quality_passes(tmp_path):
    import yaml
    epics_dir = tmp_path / "epics"
    epics_dir.mkdir()
    for i, name in enumerate(["data-loading", "model-training"], start=1):
        spec = {
            "name": name,
            "description": f"Epic for {name}",
            "acceptance_criteria": ["Criterion 1", "Criterion 2"],
            "dependencies": [],
            "estimated_steps": 3,
        }
        with open(epics_dir / f"{i:02d}-{name}.yaml", "w") as f:
            yaml.dump(spec, f)
    results = check_define_epics_quality(epics_dir)
    failures = [r for r in results if not r.passed]
    assert len(failures) == 0, f"Unexpected failures: {[r.message for r in failures]}"
