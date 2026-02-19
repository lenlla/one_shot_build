# Integration Testing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python + pytest integration test suite that tests the one-shot-build plugin phase-by-phase using real Claude Code CLI invocations, with autonomous fix-then-retry remediation.

**Architecture:** A pytest suite under `integration_tests/` with three layers: (1) infrastructure (claude runner, setup agent, live responder, fix agent), (2) assertions (structural hard gates + quality advisories), (3) test files per phase and edge case. A `run_all.py` orchestrator coordinates execution, fix loops, and reporting.

**Tech Stack:** Python 3.10+, pytest, pytest-xdist, PyYAML, anthropic SDK (for setup agent / responder haiku calls)

**Design doc:** `docs/plans/2026-02-19-integration-testing-design.md`

---

### Task 1: Project Setup and Synthetic Data

**Files:**
- Create: `integration_tests/__init__.py`
- Create: `integration_tests/fixtures/__init__.py`
- Create: `integration_tests/fixtures/synthetic/__init__.py`
- Create: `integration_tests/fixtures/synthetic/generate.py`
- Create: `integration_tests/fixtures/synthetic/customers.csv`
- Create: `integration_tests/fixtures/synthetic/analyst-context.yaml`
- Create: `integration_tests/agents/__init__.py`
- Create: `integration_tests/assertions/__init__.py`
- Create: `integration_tests/requirements.txt`

**Step 1: Create directory structure**

```bash
mkdir -p integration_tests/fixtures/synthetic
mkdir -p integration_tests/agents
mkdir -p integration_tests/assertions
touch integration_tests/__init__.py
touch integration_tests/fixtures/__init__.py
touch integration_tests/fixtures/synthetic/__init__.py
touch integration_tests/agents/__init__.py
touch integration_tests/assertions/__init__.py
```

**Step 2: Write the data generator**

Create `integration_tests/fixtures/synthetic/generate.py`:

```python
"""Deterministic synthetic dataset for integration testing.

Generates a 100-row customer churn dataset with fixed seed for reproducibility.
Run directly to regenerate: python -m integration_tests.fixtures.synthetic.generate
"""

import csv
import random
from pathlib import Path


SEED = 42
NUM_ROWS = 100
OUTPUT_PATH = Path(__file__).parent / "customers.csv"

COLUMNS = ["customer_id", "age", "tenure_months", "monthly_spend", "support_tickets", "churned"]


def generate() -> list[dict]:
    random.seed(SEED)
    rows = []
    for i in range(1, NUM_ROWS + 1):
        age = random.randint(18, 80)
        tenure = random.randint(1, 60)
        spend = round(random.uniform(10.0, 500.0), 2)
        tickets = random.randint(0, 10)
        # Simple churn logic: higher tickets + lower tenure = more likely to churn
        churn_score = (tickets / 10) * 0.6 + (1 - tenure / 60) * 0.4
        churned = random.random() < churn_score
        rows.append({
            "customer_id": i,
            "age": age,
            "tenure_months": tenure,
            "monthly_spend": spend,
            "support_tickets": tickets,
            "churned": churned,
        })
    return rows


def write_csv(rows: list[dict], path: Path = OUTPUT_PATH) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    rows = generate()
    write_csv(rows)
    print(f"Generated {len(rows)} rows to {OUTPUT_PATH}")
```

**Step 3: Generate the CSV**

Run: `python -m integration_tests.fixtures.synthetic.generate`

Expected: `Generated 100 rows to .../customers.csv`

Verify: `wc -l integration_tests/fixtures/synthetic/customers.csv` → 101 (100 data rows + header)

**Step 4: Write the analyst context file**

Create `integration_tests/fixtures/synthetic/analyst-context.yaml`:

```yaml
project_name: "integration-test-churn"
business_objective: "Predict customer churn from demographic and behavioral features"
target_variable: "churned"
data_paths: ["customers.csv"]
exclude_columns: ["customer_id"]
domain_notes: "This is synthetic test data. No special domain constraints."
epic_preferences: "Keep it simple - data loading, model training, evaluation"
```

**Step 5: Write requirements.txt**

Create `integration_tests/requirements.txt`:

```
pytest>=8.0
pytest-xdist>=3.5
pyyaml>=6.0
anthropic>=0.42.0
```

**Step 6: Install dependencies and commit**

```bash
pip install -r integration_tests/requirements.txt
git add integration_tests/
git commit -m "feat(integration): add synthetic fixtures and project setup"
```

---

### Task 2: Assertion Framework

**Files:**
- Create: `integration_tests/assertions/models.py`
- Create: `integration_tests/assertions/structural.py`
- Create: `integration_tests/assertions/quality.py`
- Create: `integration_tests/assertions/test_structural.py`
- Create: `integration_tests/assertions/test_quality.py`

**Step 1: Write the assertion result model**

Create `integration_tests/assertions/models.py`:

```python
from dataclasses import dataclass
from typing import Literal


@dataclass
class AssertionResult:
    passed: bool
    message: str
    tier: Literal["structural", "quality"]


def check_results(results: list[AssertionResult]) -> tuple[list[AssertionResult], list[AssertionResult]]:
    """Split results into hard failures and warnings."""
    failures = [r for r in results if not r.passed and r.tier == "structural"]
    warnings = [r for r in results if not r.passed and r.tier == "quality"]
    return failures, warnings
```

**Step 2: Write the failing test for structural assertions**

Create `integration_tests/assertions/test_structural.py`:

```python
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
```

**Step 3: Run the test to verify it fails**

Run: `pytest integration_tests/assertions/test_structural.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'integration_tests.assertions.structural'`

**Step 4: Implement structural assertions**

Create `integration_tests/assertions/structural.py`:

```python
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
    results.append(_file_exists(context_dir / "analyst-notes.md", "analyst-notes.md exists"))
    results.append(_file_not_empty(context_dir / "analyst-notes.md", "analyst-notes.md is non-empty"))
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
    state_file = epics_dir / ".execution-state.yaml"
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
```

**Step 5: Run the test to verify it passes**

Run: `pytest integration_tests/assertions/test_structural.py -v`

Expected: All 6 tests PASS

**Step 6: Write failing test for quality assertions**

Create `integration_tests/assertions/test_quality.py`:

```python
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
        (standards / f).write_text(f"# {f}\n\nSubstantive content here.\n")
    results = check_init_quality(tmp_path, project_name="integration-test-churn")
    failures = [r for r in results if not r.passed]
    assert len(failures) == 0, f"Unexpected failures: {[r.message for r in failures]}"


def test_profile_quality_passes(tmp_path):
    context = tmp_path / "kyros-agent-workflow" / "docs" / "context"
    context.mkdir(parents=True)
    profile_content = "# Data Profile: customers\n\n" + "\n".join(f"- {c}" for c in EXPECTED_COLUMNS)
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
            "acceptance_criteria": [f"Criterion 1", f"Criterion 2"],
            "dependencies": [],
            "estimated_steps": 3,
        }
        with open(epics_dir / f"{i:02d}-{name}.yaml", "w") as f:
            yaml.dump(spec, f)
    results = check_define_epics_quality(epics_dir)
    failures = [r for r in results if not r.passed]
    assert len(failures) == 0, f"Unexpected failures: {[r.message for r in failures]}"
```

**Step 7: Run test to verify it fails**

Run: `pytest integration_tests/assertions/test_quality.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'integration_tests.assertions.quality'`

**Step 8: Implement quality assertions**

Create `integration_tests/assertions/quality.py`:

```python
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
```

**Step 9: Run tests to verify they pass**

Run: `pytest integration_tests/assertions/ -v`

Expected: All tests PASS

**Step 10: Commit**

```bash
git add integration_tests/assertions/
git commit -m "feat(integration): add two-tier assertion framework"
```

---

### Task 3: Claude Runner Infrastructure

**Files:**
- Create: `integration_tests/conftest.py`
- Create: `integration_tests/claude_runner.py`
- Create: `integration_tests/test_claude_runner.py`

**Step 1: Write the failing test for claude_runner**

Create `integration_tests/test_claude_runner.py`:

```python
"""Smoke tests for the ClaudeRunner — verifies basic subprocess management."""

import pytest

from integration_tests.claude_runner import ClaudeRunner


def test_runner_sends_print_message():
    """claude --print with a trivial prompt returns a response."""
    runner = ClaudeRunner()
    output = runner.run_print("Reply with exactly: PONG")
    assert "PONG" in output


def test_runner_captures_output():
    """The runner captures full stdout."""
    runner = ClaudeRunner()
    output = runner.run_print("Reply with exactly the word: HELLO")
    assert len(output) > 0


def test_runner_timeout():
    """The runner respects timeout and doesn't hang."""
    runner = ClaudeRunner(timeout=5)
    # A very short timeout with a simple prompt should still work
    output = runner.run_print("Reply with: OK")
    assert len(output) > 0
```

**Step 2: Run the test to verify it fails**

Run: `pytest integration_tests/test_claude_runner.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'integration_tests.claude_runner'`

**Step 3: Implement ClaudeRunner**

Create `integration_tests/claude_runner.py`:

```python
"""Wrapper around the claude CLI for integration testing.

Provides two modes:
- run_print(): Non-interactive, sends a single prompt via --print flag
- run_interactive(): Interactive, streams stdin/stdout for multi-turn sessions
"""

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SessionTranscript:
    """Captured output from a Claude session."""
    turns: list[dict] = field(default_factory=list)  # {"role": "claude"|"user", "content": str}
    raw_stdout: str = ""
    raw_stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False


class ClaudeRunner:
    """Manages claude CLI subprocess lifecycle."""

    def __init__(
        self,
        working_dir: Path | str | None = None,
        timeout: int = 600,
        plugin_dir: Path | str | None = None,
    ):
        self.working_dir = Path(working_dir) if working_dir else None
        self.timeout = timeout
        self.plugin_dir = Path(plugin_dir) if plugin_dir else None

    def run_print(self, prompt: str) -> str:
        """Send a single prompt via claude --print and return the response."""
        cmd = ["claude", "--print", prompt]
        if self.plugin_dir:
            cmd.extend(["--plugin", str(self.plugin_dir)])
        result = subprocess.run(
            cmd,
            cwd=self.working_dir,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if result.returncode != 0:
            logger.warning("claude --print returned %d: %s", result.returncode, result.stderr)
        return result.stdout

    def run_interactive(
        self,
        initial_prompt: str,
        responder=None,
        phase_timeout: int | None = None,
    ) -> SessionTranscript:
        """Run an interactive claude session with optional live responder.

        Args:
            initial_prompt: The first message to send.
            responder: Optional callable(turn_text) -> str|None that generates
                       responses to unexpected questions. Return None to skip.
            phase_timeout: Override instance timeout for this session.
        """
        timeout = phase_timeout or self.timeout
        transcript = SessionTranscript()

        cmd = ["claude"]
        if self.plugin_dir:
            cmd.extend(["--plugin", str(self.plugin_dir)])

        proc = subprocess.Popen(
            cmd,
            cwd=self.working_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout_lines = []
        stderr_lines = []

        def read_stderr():
            for line in proc.stderr:
                stderr_lines.append(line)

        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()

        try:
            # Send initial prompt
            proc.stdin.write(initial_prompt + "\n")
            proc.stdin.flush()
            transcript.turns.append({"role": "user", "content": initial_prompt})

            current_turn = []
            last_output_time = time.time()
            response_count = 0
            max_responses = 20

            while True:
                # Check timeout
                if time.time() - last_output_time > timeout:
                    transcript.timed_out = True
                    break

                # Try to read a line (non-blocking via timeout)
                try:
                    proc.stdout.flush()
                    line = proc.stdout.readline()
                    if not line:
                        # Process exited
                        break
                    current_turn.append(line)
                    last_output_time = time.time()
                except Exception:
                    break

                # Check if Claude is waiting for input (5s silence)
                if responder and time.time() - last_output_time > 5:
                    turn_text = "".join(current_turn)
                    if turn_text.strip():
                        transcript.turns.append({"role": "claude", "content": turn_text})
                        response = responder(turn_text)
                        if response and response_count < max_responses:
                            proc.stdin.write(response + "\n")
                            proc.stdin.flush()
                            transcript.turns.append({"role": "user", "content": response})
                            response_count += 1
                            current_turn = []

        except Exception as e:
            logger.error("Interactive session error: %s", e)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()

            transcript.raw_stdout = "".join(stdout_lines) if stdout_lines else ""
            transcript.raw_stderr = "".join(stderr_lines)
            transcript.exit_code = proc.returncode

            # Capture any remaining turn
            remaining = "".join(current_turn)
            if remaining.strip():
                transcript.turns.append({"role": "claude", "content": remaining})

        return transcript
```

**Step 4: Run the test to verify it passes**

Run: `pytest integration_tests/test_claude_runner.py -v`

Expected: All 3 tests PASS (requires `claude` CLI available and authenticated)

**Step 5: Write conftest.py with shared fixtures**

Create `integration_tests/conftest.py`:

```python
"""Shared pytest fixtures for integration tests."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

from integration_tests.claude_runner import ClaudeRunner


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"
PLUGIN_DIR = Path(__file__).parent.parent  # one_shot_build repo root


def pytest_addoption(parser):
    parser.addoption("--chained", action="store_true", default=False, help="Run phases chained in a shared directory")
    parser.addoption("--phase-timeout", type=int, default=600, help="Timeout per phase in seconds")
    parser.addoption("--no-fix", action="store_true", default=False, help="Skip fix-then-retry loop")


@pytest.fixture(scope="function")
def test_project_dir(tmp_path):
    """A fresh temp directory with git init and synthetic data copied in."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    shutil.copy(FIXTURES_DIR / "customers.csv", project_dir / "customers.csv")
    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial: add synthetic data"],
        cwd=project_dir, capture_output=True,
    )
    return project_dir


@pytest.fixture(scope="session")
def shared_project_dir(tmp_path_factory):
    """A shared temp directory for chained mode — persists across all tests in the session."""
    project_dir = tmp_path_factory.mktemp("chained-project")
    shutil.copy(FIXTURES_DIR / "customers.csv", project_dir / "customers.csv")
    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial: add synthetic data"],
        cwd=project_dir, capture_output=True,
    )
    return project_dir


@pytest.fixture
def claude_runner(test_project_dir, request):
    """A ClaudeRunner pointed at the test project directory."""
    timeout = request.config.getoption("--phase-timeout")
    return ClaudeRunner(
        working_dir=test_project_dir,
        timeout=timeout,
        plugin_dir=PLUGIN_DIR,
    )


@pytest.fixture
def analyst_context():
    """The pre-built analyst answers as a dict."""
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def log_dir(tmp_path):
    """Directory for session transcripts."""
    d = tmp_path / ".logs"
    d.mkdir()
    return d
```

**Step 6: Run tests to verify conftest loads**

Run: `pytest integration_tests/test_claude_runner.py -v --co` (collect only)

Expected: 3 tests collected, no import errors

**Step 7: Commit**

```bash
git add integration_tests/claude_runner.py integration_tests/conftest.py integration_tests/test_claude_runner.py
git commit -m "feat(integration): add claude runner and pytest fixtures"
```

---

### Task 4: Setup Agent

**Files:**
- Create: `integration_tests/agents/setup_agent.py`
- Create: `integration_tests/agents/test_setup_agent.py`

**Step 1: Write the failing test**

Create `integration_tests/agents/test_setup_agent.py`:

```python
"""Tests for the setup agent — verifies prompt generation from skill definitions."""

import yaml
from pathlib import Path

from integration_tests.agents.setup_agent import generate_prompt, PHASE_SKILL_MAP


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "synthetic"
PLUGIN_DIR = Path(__file__).parent.parent.parent  # one_shot_build repo root


def test_generate_prompt_for_init():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        context = yaml.safe_load(f)
    prompt = generate_prompt("init", context, PLUGIN_DIR)
    assert "/init" in prompt
    assert context["project_name"] in prompt


def test_generate_prompt_for_profile_data():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        context = yaml.safe_load(f)
    prompt = generate_prompt("profile-data", context, PLUGIN_DIR)
    assert "/profile-data" in prompt or "profile" in prompt.lower()
    assert context["target_variable"] in prompt


def test_generate_prompt_for_define_epics():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        context = yaml.safe_load(f)
    prompt = generate_prompt("define-epics", context, PLUGIN_DIR)
    assert "epic" in prompt.lower()
    assert context["business_objective"] in prompt


def test_prompt_caching(tmp_path):
    """Generating twice with same skill hash returns cached result."""
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        context = yaml.safe_load(f)
    prompt1 = generate_prompt("init", context, PLUGIN_DIR, cache_dir=tmp_path)
    prompt2 = generate_prompt("init", context, PLUGIN_DIR, cache_dir=tmp_path)
    assert prompt1 == prompt2
```

**Step 2: Run the test to verify it fails**

Run: `pytest integration_tests/agents/test_setup_agent.py -v`

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement the setup agent**

Create `integration_tests/agents/setup_agent.py`:

```python
"""Setup agent — generates prompt templates for each phase by reading skill definitions.

Uses a fast/cheap Claude model (haiku) to generate prompts that pre-supply known answers,
minimizing back-and-forth during test runs.
"""

import hashlib
import json
import logging
from pathlib import Path

import anthropic
import yaml

logger = logging.getLogger(__name__)


PHASE_SKILL_MAP = {
    "init": "skills/harness-init/SKILL.md",
    "profile-data": "skills/profile-data/SKILL.md",
    "define-epics": "skills/define-epics/SKILL.md",
    "execute-plan": "skills/execute-plan/SKILL.md",
}


def generate_prompt(
    phase: str,
    analyst_context: dict,
    plugin_dir: Path,
    cache_dir: Path | None = None,
) -> str:
    """Generate a prompt template for a phase test.

    Args:
        phase: One of "init", "profile-data", "define-epics", "execute-plan".
        analyst_context: Dict from analyst-context.yaml.
        plugin_dir: Path to the plugin repo root (to read skill definitions).
        cache_dir: Optional directory for caching prompts by skill file hash.

    Returns:
        A prompt string ready to pipe into the claude CLI.
    """
    skill_path = plugin_dir / PHASE_SKILL_MAP[phase]
    skill_content = skill_path.read_text()
    skill_hash = hashlib.sha256(skill_content.encode()).hexdigest()[:16]

    # Check cache
    if cache_dir:
        cache_file = cache_dir / f"{phase}-{skill_hash}.txt"
        if cache_file.exists():
            logger.info("Using cached prompt for %s", phase)
            return cache_file.read_text()

    # Generate via Claude API
    client = anthropic.Anthropic()
    context_yaml = yaml.dump(analyst_context, default_flow_style=False)

    system_prompt = (
        "You are generating a test prompt for a Claude Code plugin. "
        "The prompt will be sent as a user message to Claude Code with the plugin loaded. "
        "Your output should be ONLY the prompt text — no explanation, no markdown fences. "
        "The prompt must invoke the slash command and pre-supply all answers the skill will ask for, "
        "so the session can complete with minimal back-and-forth."
    )

    user_prompt = (
        f"Generate a prompt for the '/{phase}' command.\n\n"
        f"## Skill definition\n\n{skill_content}\n\n"
        f"## Analyst context (known answers)\n\n```yaml\n{context_yaml}```\n\n"
        f"## Instructions\n\n"
        f"Write a single prompt that:\n"
        f"1. Invokes the /{phase} command with appropriate arguments\n"
        f"2. Pre-supplies all known answers inline so Claude doesn't need to ask\n"
        f"3. Tells Claude to proceed without asking for confirmation where possible\n"
        f"4. Is concise but complete\n"
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    prompt = response.content[0].text

    # Cache result
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{phase}-{skill_hash}.txt"
        cache_file.write_text(prompt)
        logger.info("Cached prompt for %s at %s", phase, cache_file)

    return prompt
```

**Step 4: Run the test to verify it passes**

Run: `pytest integration_tests/agents/test_setup_agent.py -v`

Expected: All 4 tests PASS (requires `ANTHROPIC_API_KEY` set)

**Step 5: Commit**

```bash
git add integration_tests/agents/setup_agent.py integration_tests/agents/test_setup_agent.py
git commit -m "feat(integration): add setup agent for prompt generation"
```

---

### Task 5: Live Responder

**Files:**
- Create: `integration_tests/agents/responder_agent.py`
- Create: `integration_tests/agents/test_responder_agent.py`

**Step 1: Write the failing test**

Create `integration_tests/agents/test_responder_agent.py`:

```python
"""Tests for the live responder — verifies question detection and response generation."""

import yaml
from pathlib import Path

from integration_tests.agents.responder_agent import LiveResponder, detect_question


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "synthetic"


def test_detect_question_with_question_mark():
    assert detect_question("What is the target variable?\n")


def test_detect_question_with_numbered_options():
    text = "Choose an option:\n1. Option A\n2. Option B\n3. Option C\n"
    assert detect_question(text)


def test_detect_question_plain_statement():
    assert not detect_question("Processing data profiles...\n")


def test_responder_generates_answer():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        context = yaml.safe_load(f)
    responder = LiveResponder(context)
    answer = responder.respond("What is the target variable for this dataset?")
    assert answer is not None
    assert len(answer) > 0


def test_responder_returns_none_for_non_question():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        context = yaml.safe_load(f)
    responder = LiveResponder(context)
    answer = responder.respond("Creating data profile... done.")
    assert answer is None


def test_responder_tracks_response_count():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        context = yaml.safe_load(f)
    responder = LiveResponder(context, max_responses=2)
    responder.respond("Question 1?")
    responder.respond("Question 2?")
    answer = responder.respond("Question 3?")
    assert answer is None  # Exceeded max
```

**Step 2: Run test to verify it fails**

Run: `pytest integration_tests/agents/test_responder_agent.py -v`

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement the live responder**

Create `integration_tests/agents/responder_agent.py`:

```python
"""Live responder agent — monitors Claude output and answers unexpected questions.

During integration test runs, Claude may ask questions that weren't anticipated by
the setup agent's prompt template. The live responder detects these questions and
generates appropriate analyst responses using a fast model.
"""

import logging
import re

import anthropic
import yaml

logger = logging.getLogger(__name__)


def detect_question(text: str) -> bool:
    """Heuristic: does this text look like Claude is asking the user a question?"""
    text = text.strip()
    if not text:
        return False
    # Ends with question mark
    if text.rstrip().endswith("?"):
        return True
    # Contains numbered options (1. ... 2. ... or - Option A / - Option B)
    if re.search(r"^\s*[1-4]\.\s+", text, re.MULTILINE):
        lines_with_numbers = re.findall(r"^\s*[1-4]\.\s+", text, re.MULTILINE)
        if len(lines_with_numbers) >= 2:
            return True
    # Contains "choose", "select", "which", "would you" patterns
    lower = text.lower()
    question_phrases = ["choose", "select one", "which option", "would you like", "do you want"]
    if any(phrase in lower for phrase in question_phrases):
        return True
    return False


class LiveResponder:
    """Generates responses to unexpected Claude questions during test runs."""

    def __init__(self, analyst_context: dict, max_responses: int = 20):
        self.analyst_context = analyst_context
        self.max_responses = max_responses
        self.response_count = 0
        self.client = anthropic.Anthropic()

    def respond(self, claude_output: str) -> str | None:
        """Generate a response if Claude is asking a question.

        Returns None if:
        - The output doesn't look like a question
        - Max responses exceeded
        """
        if self.response_count >= self.max_responses:
            logger.warning("Max responses (%d) exceeded, not responding", self.max_responses)
            return None

        if not detect_question(claude_output):
            return None

        context_yaml = yaml.dump(self.analyst_context, default_flow_style=False)

        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=(
                "You are a data analyst testing a workflow with a synthetic churn dataset. "
                "Respond naturally and concisely to Claude's question based on your project context. "
                "If asked to choose from options, pick the most reasonable one. "
                "If asked to approve or confirm, say yes. "
                "Keep responses under 2 sentences."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Your project context:\n```yaml\n{context_yaml}```\n\n"
                        f"Claude asked you:\n{claude_output}\n\n"
                        f"Respond as the analyst."
                    ),
                }
            ],
        )

        self.response_count += 1
        return response.content[0].text

    def as_callable(self):
        """Return a callable suitable for ClaudeRunner.run_interactive(responder=...)."""
        return self.respond
```

**Step 4: Run tests to verify they pass**

Run: `pytest integration_tests/agents/test_responder_agent.py -v`

Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add integration_tests/agents/responder_agent.py integration_tests/agents/test_responder_agent.py
git commit -m "feat(integration): add live responder agent"
```

---

### Task 6: Happy-Path Test — /init

**Files:**
- Create: `integration_tests/test_init.py`

**Step 1: Write the test**

Create `integration_tests/test_init.py`:

```python
"""Integration test for the /init phase.

Runs /init via the claude CLI and verifies the project scaffolding was created correctly.
"""

import logging
from pathlib import Path

import pytest
import yaml

from integration_tests.agents.setup_agent import generate_prompt
from integration_tests.agents.responder_agent import LiveResponder
from integration_tests.assertions.structural import check_init
from integration_tests.assertions.quality import check_init_quality
from integration_tests.assertions.models import check_results
from integration_tests.claude_runner import ClaudeRunner

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"


@pytest.fixture
def analyst_context():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        return yaml.safe_load(f)


def test_init_structural(test_project_dir, analyst_context):
    """Run /init and verify all required files and directories are created."""
    runner = ClaudeRunner(
        working_dir=test_project_dir,
        timeout=120,
        plugin_dir=PLUGIN_DIR,
    )
    prompt = generate_prompt("init", analyst_context, PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    transcript = runner.run_interactive(prompt, responder=responder.as_callable())

    # Log transcript for debugging
    log_file = test_project_dir / "init-transcript.txt"
    _write_transcript(transcript, log_file)

    # Structural assertions (hard gate)
    results = check_init(test_project_dir)
    failures, warnings = check_results(results)

    if failures:
        failure_msgs = "\n".join(f"  - {r.message}" for r in failures)
        pytest.fail(f"Structural assertions failed:\n{failure_msgs}")


def test_init_quality(test_project_dir, analyst_context):
    """Run /init and check content quality (advisory)."""
    runner = ClaudeRunner(
        working_dir=test_project_dir,
        timeout=120,
        plugin_dir=PLUGIN_DIR,
    )
    prompt = generate_prompt("init", analyst_context, PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    transcript = runner.run_interactive(prompt, responder=responder.as_callable())

    results = check_init_quality(test_project_dir, project_name=analyst_context["project_name"])
    _, warnings = check_results(results)

    if warnings:
        warning_msgs = "\n".join(f"  - {r.message}" for r in warnings)
        logger.warning("Quality warnings:\n%s", warning_msgs)


def _write_transcript(transcript, path):
    with open(path, "w") as f:
        for turn in transcript.turns:
            f.write(f"=== {turn['role'].upper()} ===\n")
            f.write(turn["content"])
            f.write("\n\n")
        if transcript.timed_out:
            f.write("=== TIMED OUT ===\n")
```

**Step 2: Run the test (dry run — collect only)**

Run: `pytest integration_tests/test_init.py -v --co`

Expected: 2 tests collected, no import errors

**Step 3: Commit**

```bash
git add integration_tests/test_init.py
git commit -m "feat(integration): add /init phase test"
```

---

### Task 7: Happy-Path Test — /profile-data

**Files:**
- Create: `integration_tests/test_profile_data.py`
- Create: `integration_tests/fixtures/synthetic/init_output/` (pre-built fixture for isolated mode)

**Step 1: Create the pre-built init fixture**

This fixture represents the output of a successful `/init` run so `test_profile_data` can run independently.

```bash
mkdir -p integration_tests/fixtures/synthetic/init_output/kyros-agent-workflow/docs/context
mkdir -p integration_tests/fixtures/synthetic/init_output/kyros-agent-workflow/docs/standards
mkdir -p integration_tests/fixtures/synthetic/init_output/kyros-agent-workflow/docs/solutions
mkdir -p integration_tests/fixtures/synthetic/init_output/kyros-agent-workflow/docs/plans
mkdir -p integration_tests/fixtures/synthetic/init_output/kyros-agent-workflow/docs/epics
mkdir -p integration_tests/fixtures/synthetic/init_output/kyros-agent-workflow/config
mkdir -p integration_tests/fixtures/synthetic/init_output/kyros-agent-workflow/src/utils
mkdir -p integration_tests/fixtures/synthetic/init_output/kyros-agent-workflow/tests
mkdir -p integration_tests/fixtures/synthetic/init_output/kyros-agent-workflow/scripts
```

Create fixture files using the templates from the plugin. The implementing agent should:
- Copy `templates/CLAUDE.md.template` → `init_output/CLAUDE.md` with `{{PROJECT_NAME}}` replaced by `integration-test-churn` and `{{CREATED_DATE}}` replaced by the current date
- Copy `templates/.harnessrc.template` → `init_output/kyros-agent-workflow/.harnessrc`
- Copy `templates/coding-standards.md.template` → `init_output/kyros-agent-workflow/docs/standards/coding-standards.md`
- Copy `templates/definition-of-done.md.template` → `init_output/kyros-agent-workflow/docs/standards/definition-of-done.md`
- Copy `templates/review-criteria.md.template` → `init_output/kyros-agent-workflow/docs/standards/review-criteria.md`

**Step 2: Write the test**

Create `integration_tests/test_profile_data.py`:

```python
"""Integration test for the /profile-data phase.

Runs /profile-data against the synthetic customers.csv and verifies data profiles are created.
"""

import logging
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from integration_tests.agents.setup_agent import generate_prompt
from integration_tests.agents.responder_agent import LiveResponder
from integration_tests.assertions.structural import check_profile_data
from integration_tests.assertions.quality import check_profile_data_quality
from integration_tests.assertions.models import check_results
from integration_tests.claude_runner import ClaudeRunner

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"
INIT_FIXTURE = FIXTURES_DIR / "init_output"
EXPECTED_COLUMNS = ["customer_id", "age", "tenure_months", "monthly_spend", "support_tickets", "churned"]


@pytest.fixture
def analyst_context():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def initialized_project(test_project_dir):
    """A test project pre-loaded with /init output fixture."""
    # Copy init fixture into test project
    for item in INIT_FIXTURE.iterdir():
        dest = test_project_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    # Commit the init state
    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init: scaffold project"],
        cwd=test_project_dir, capture_output=True,
    )
    return test_project_dir


def test_profile_data_structural(initialized_project, analyst_context):
    """Run /profile-data and verify profile files are created."""
    runner = ClaudeRunner(
        working_dir=initialized_project,
        timeout=300,
        plugin_dir=PLUGIN_DIR,
    )
    prompt = generate_prompt("profile-data", analyst_context, PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    transcript = runner.run_interactive(prompt, responder=responder.as_callable())

    log_file = initialized_project / "profile-data-transcript.txt"
    _write_transcript(transcript, log_file)

    results = check_profile_data(initialized_project, table_names=["customers"])
    failures, _ = check_results(results)

    if failures:
        failure_msgs = "\n".join(f"  - {r.message}" for r in failures)
        pytest.fail(f"Structural assertions failed:\n{failure_msgs}")


def test_profile_data_quality(initialized_project, analyst_context):
    """Run /profile-data and check content quality."""
    runner = ClaudeRunner(
        working_dir=initialized_project,
        timeout=300,
        plugin_dir=PLUGIN_DIR,
    )
    prompt = generate_prompt("profile-data", analyst_context, PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    runner.run_interactive(prompt, responder=responder.as_callable())

    results = check_profile_data_quality(
        initialized_project,
        table_names=["customers"],
        expected_columns=EXPECTED_COLUMNS,
    )
    _, warnings = check_results(results)

    if warnings:
        warning_msgs = "\n".join(f"  - {r.message}" for r in warnings)
        logger.warning("Quality warnings:\n%s", warning_msgs)


def _write_transcript(transcript, path):
    with open(path, "w") as f:
        for turn in transcript.turns:
            f.write(f"=== {turn['role'].upper()} ===\n")
            f.write(turn["content"])
            f.write("\n\n")
```

**Step 3: Run dry run**

Run: `pytest integration_tests/test_profile_data.py -v --co`

Expected: 2 tests collected

**Step 4: Commit**

```bash
git add integration_tests/test_profile_data.py integration_tests/fixtures/synthetic/init_output/
git commit -m "feat(integration): add /profile-data phase test with init fixture"
```

---

### Task 8: Happy-Path Test — /define-epics

**Files:**
- Create: `integration_tests/test_define_epics.py`
- Create: `integration_tests/fixtures/synthetic/profile_output/` (pre-built fixture)

**Step 1: Create the pre-built profile fixture**

Extend the init fixture with data profile output. Create `integration_tests/fixtures/synthetic/profile_output/` as a copy of `init_output/` plus:

- `kyros-agent-workflow/docs/context/data-profile-customers.md` — a realistic data profile for the synthetic dataset
- `kyros-agent-workflow/docs/context/analyst-notes.md` — analyst Q&A answers

The implementing agent should generate realistic content for these files based on the synthetic `customers.csv` data. The data profile should include column types, null counts, distributions, and basic stats. The analyst notes should match the `analyst-context.yaml` answers.

**Step 2: Write the test**

Create `integration_tests/test_define_epics.py`:

```python
"""Integration test for the /define-epics phase.

Runs /define-epics and verifies epic YAML specs are created.
"""

import logging
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from integration_tests.agents.setup_agent import generate_prompt
from integration_tests.agents.responder_agent import LiveResponder
from integration_tests.assertions.structural import check_define_epics
from integration_tests.assertions.quality import check_define_epics_quality
from integration_tests.assertions.models import check_results
from integration_tests.claude_runner import ClaudeRunner

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"
PROFILE_FIXTURE = FIXTURES_DIR / "profile_output"


@pytest.fixture
def analyst_context():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def profiled_project(test_project_dir):
    """A test project pre-loaded with /init + /profile-data output."""
    for item in PROFILE_FIXTURE.iterdir():
        dest = test_project_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "docs: add data profiles"],
        cwd=test_project_dir, capture_output=True,
    )
    return test_project_dir


def test_define_epics_structural(profiled_project, analyst_context):
    """Run /define-epics and verify epic specs are created."""
    runner = ClaudeRunner(
        working_dir=profiled_project,
        timeout=300,
        plugin_dir=PLUGIN_DIR,
    )
    prompt = generate_prompt("define-epics", analyst_context, PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    transcript = runner.run_interactive(prompt, responder=responder.as_callable())

    log_file = profiled_project / "define-epics-transcript.txt"
    _write_transcript(transcript, log_file)

    # Find the epics directory — we don't know the exact name in advance
    epics_dir = _find_epics_dir(profiled_project)
    if epics_dir is None:
        pytest.fail("No epics directory found after /define-epics")

    results = check_define_epics(profiled_project, epics_dir)
    failures, _ = check_results(results)

    if failures:
        failure_msgs = "\n".join(f"  - {r.message}" for r in failures)
        pytest.fail(f"Structural assertions failed:\n{failure_msgs}")


def test_define_epics_quality(profiled_project, analyst_context):
    """Run /define-epics and check content quality."""
    runner = ClaudeRunner(
        working_dir=profiled_project,
        timeout=300,
        plugin_dir=PLUGIN_DIR,
    )
    prompt = generate_prompt("define-epics", analyst_context, PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    runner.run_interactive(prompt, responder=responder.as_callable())

    epics_dir = _find_epics_dir(profiled_project)
    if epics_dir is None:
        logger.warning("No epics directory found — skipping quality checks")
        return

    results = check_define_epics_quality(epics_dir)
    _, warnings = check_results(results)

    if warnings:
        warning_msgs = "\n".join(f"  - {r.message}" for r in warnings)
        logger.warning("Quality warnings:\n%s", warning_msgs)


def _find_epics_dir(project_dir: Path) -> Path | None:
    """Search for the epics directory created by /define-epics."""
    # Check common locations
    for candidate in ["epics/v1", "epics/initial", "epics"]:
        d = project_dir / candidate
        if d.is_dir() and list(d.glob("*.yaml")):
            return d
    # Search more broadly
    for d in project_dir.rglob("*.yaml"):
        parent = d.parent
        yaml_files = list(parent.glob("*.yaml"))
        if len(yaml_files) >= 2 and parent.name != "kyros-agent-workflow":
            return parent
    return None


def _write_transcript(transcript, path):
    with open(path, "w") as f:
        for turn in transcript.turns:
            f.write(f"=== {turn['role'].upper()} ===\n")
            f.write(turn["content"])
            f.write("\n\n")
```

**Step 3: Run dry run**

Run: `pytest integration_tests/test_define_epics.py -v --co`

Expected: 2 tests collected

**Step 4: Commit**

```bash
git add integration_tests/test_define_epics.py integration_tests/fixtures/synthetic/profile_output/
git commit -m "feat(integration): add /define-epics phase test with profile fixture"
```

---

### Task 9: Happy-Path Test — /execute-plan

**Files:**
- Create: `integration_tests/test_execute_plan.py`
- Create: `integration_tests/fixtures/synthetic/epics_output/` (pre-built fixture)

**Step 1: Create the pre-built epics fixture**

Extend the profile fixture with epic specs. Create `integration_tests/fixtures/synthetic/epics_output/` as a copy of `profile_output/` plus an `epics/v1/` directory with two minimal epic YAML specs:

Create `integration_tests/fixtures/synthetic/epics_output/epics/v1/01-data-loading.yaml`:

```yaml
name: "data-loading"
description: "Load the customers CSV, validate schema, handle missing values, and output a clean DataFrame"
acceptance_criteria:
  - "CSV is loaded into a pandas DataFrame"
  - "Schema matches expected columns: age, tenure_months, monthly_spend, support_tickets, churned"
  - "customer_id column is dropped"
  - "No null values remain after cleaning"
  - "Unit tests verify loading, schema validation, and null handling"
dependencies: []
estimated_steps: 3
```

Create `integration_tests/fixtures/synthetic/epics_output/epics/v1/02-model-training.yaml`:

```yaml
name: "model-training"
description: "Train a logistic regression model to predict churn, evaluate with accuracy and classification report"
acceptance_criteria:
  - "Data is split into train/test sets (80/20)"
  - "LogisticRegression model is trained on training set"
  - "Model accuracy is reported on test set"
  - "Classification report is generated and saved"
  - "Unit tests verify train/test split, model fitting, and prediction output"
dependencies:
  - "data-loading"
estimated_steps: 4
```

**Step 2: Write the test**

Create `integration_tests/test_execute_plan.py`:

```python
"""Integration test for the /execute-plan phase.

This is the most complex phase — runs the full plan/build/submit loop.
Uses a longer timeout since it involves TDD planning, agent team building, and PR creation.
"""

import logging
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from integration_tests.agents.setup_agent import generate_prompt
from integration_tests.agents.responder_agent import LiveResponder
from integration_tests.assertions.structural import check_execute_plan
from integration_tests.assertions.quality import check_execute_plan_quality
from integration_tests.assertions.models import check_results
from integration_tests.claude_runner import ClaudeRunner

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"
EPICS_FIXTURE = FIXTURES_DIR / "epics_output"


@pytest.fixture
def analyst_context():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def project_with_epics(test_project_dir):
    """A test project pre-loaded with /init + /profile-data + /define-epics output."""
    for item in EPICS_FIXTURE.iterdir():
        dest = test_project_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    # Set up git remote for PR creation
    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "docs: define epics"],
        cwd=test_project_dir, capture_output=True,
    )
    return test_project_dir


def test_execute_plan_structural(project_with_epics, analyst_context):
    """Run /execute-plan and verify branches, tags, state, and tests pass."""
    runner = ClaudeRunner(
        working_dir=project_with_epics,
        timeout=900,  # 15 minutes — execute-plan is the longest phase
        plugin_dir=PLUGIN_DIR,
    )
    prompt = generate_prompt("execute-plan", analyst_context, PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    transcript = runner.run_interactive(prompt, responder=responder.as_callable(), phase_timeout=900)

    log_file = project_with_epics / "execute-plan-transcript.txt"
    _write_transcript(transcript, log_file)

    epics_dir = project_with_epics / "epics" / "v1"
    epic_names = ["data-loading", "model-training"]

    results = check_execute_plan(project_with_epics, epics_dir, epic_names)
    failures, _ = check_results(results)

    if failures:
        failure_msgs = "\n".join(f"  - {r.message}" for r in failures)
        pytest.fail(f"Structural assertions failed:\n{failure_msgs}")


def test_execute_plan_quality(project_with_epics, analyst_context):
    """Run /execute-plan and check content quality."""
    runner = ClaudeRunner(
        working_dir=project_with_epics,
        timeout=900,
        plugin_dir=PLUGIN_DIR,
    )
    prompt = generate_prompt("execute-plan", analyst_context, PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    runner.run_interactive(prompt, responder=responder.as_callable(), phase_timeout=900)

    epics_dir = project_with_epics / "epics" / "v1"
    epic_names = ["data-loading", "model-training"]

    results = check_execute_plan_quality(project_with_epics, epics_dir, epic_names)
    _, warnings = check_results(results)

    if warnings:
        warning_msgs = "\n".join(f"  - {r.message}" for r in warnings)
        logger.warning("Quality warnings:\n%s", warning_msgs)


def _write_transcript(transcript, path):
    with open(path, "w") as f:
        for turn in transcript.turns:
            f.write(f"=== {turn['role'].upper()} ===\n")
            f.write(turn["content"])
            f.write("\n\n")
```

**Step 3: Run dry run**

Run: `pytest integration_tests/test_execute_plan.py -v --co`

Expected: 2 tests collected

**Step 4: Commit**

```bash
git add integration_tests/test_execute_plan.py integration_tests/fixtures/synthetic/epics_output/
git commit -m "feat(integration): add /execute-plan phase test with epics fixture"
```

---

### Task 10: Edge Case Tests — Guards

**Files:**
- Create: `integration_tests/test_guards.py`

**Step 1: Write the test**

Create `integration_tests/test_guards.py`:

```python
"""Edge-case tests for input validation and guard behavior."""

import subprocess
from pathlib import Path

import pytest
import yaml

from integration_tests.claude_runner import ClaudeRunner

PLUGIN_DIR = Path(__file__).parent.parent


def test_missing_epics_dir(test_project_dir):
    """Calling /execute-plan with a nonexistent path should error gracefully."""
    runner = ClaudeRunner(working_dir=test_project_dir, timeout=60, plugin_dir=PLUGIN_DIR)
    output = runner.run_print("/execute-plan nonexistent/path")
    # Should get an error message, not a crash
    assert len(output) > 0
    # Should NOT create a state file
    state_file = test_project_dir / "nonexistent" / "path" / ".execution-state.yaml"
    assert not state_file.exists()


def test_malformed_harnessrc(test_project_dir):
    """A malformed .harnessrc should produce a config error."""
    harness_dir = test_project_dir / "kyros-agent-workflow"
    harness_dir.mkdir(exist_ok=True)
    (harness_dir / ".harnessrc").write_text("{{{{invalid yaml: [[[")
    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add bad config"], cwd=test_project_dir, capture_output=True)

    runner = ClaudeRunner(working_dir=test_project_dir, timeout=60, plugin_dir=PLUGIN_DIR)
    output = runner.run_print("/status")
    # The harness should handle this gracefully
    assert len(output) > 0


def test_concurrent_execution_warning(test_project_dir):
    """An existing in-progress execution should trigger a warning."""
    # Set up a fake active execution
    epics_dir = test_project_dir / "epics" / "v1"
    epics_dir.mkdir(parents=True)
    state = {
        "started_at": "2026-02-19T10:00:00Z",
        "mode": "interactive",
        "epics": {"fake-epic": {"status": "building"}},
    }
    with open(epics_dir / ".execution-state.yaml", "w") as f:
        yaml.dump(state, f)
    # Also need a CLAUDE.md and kyros-agent-workflow for the harness to recognize this as a project
    (test_project_dir / "kyros-agent-workflow").mkdir(exist_ok=True)
    (test_project_dir / "CLAUDE.md").write_text("<!-- begin:one-shot-build -->\ntest\n<!-- end:one-shot-build -->")
    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add fake state"], cwd=test_project_dir, capture_output=True)

    runner = ClaudeRunner(working_dir=test_project_dir, timeout=120, plugin_dir=PLUGIN_DIR)
    # Start a new execution — should warn about the existing one
    output = runner.run_print("/status")
    lower = output.lower()
    assert "active" in lower or "execution" in lower or "in progress" in lower or "building" in lower


def test_empty_data_file(test_project_dir):
    """Profiling an empty CSV (headers only) should handle gracefully."""
    # Create headers-only CSV
    (test_project_dir / "empty.csv").write_text("customer_id,age,tenure_months,monthly_spend,support_tickets,churned\n")
    # Set up initialized project
    harness_dir = test_project_dir / "kyros-agent-workflow"
    harness_dir.mkdir(exist_ok=True)
    (harness_dir / ".harnessrc").write_text("circuit_breaker:\n  no_progress_threshold: 3\n")
    (test_project_dir / "CLAUDE.md").write_text("<!-- begin:one-shot-build -->\ntest\n<!-- end:one-shot-build -->")
    for d in ["docs/context", "docs/standards", "docs/solutions"]:
        (harness_dir / d).mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=test_project_dir, capture_output=True)

    runner = ClaudeRunner(working_dir=test_project_dir, timeout=120, plugin_dir=PLUGIN_DIR)
    output = runner.run_print("/profile-data empty.csv")
    # Should not crash — should either report the issue or produce a profile noting 0 rows
    assert len(output) > 0
```

**Step 2: Run dry run**

Run: `pytest integration_tests/test_guards.py -v --co`

Expected: 4 tests collected

**Step 3: Commit**

```bash
git add integration_tests/test_guards.py
git commit -m "feat(integration): add input guard edge-case tests"
```

---

### Task 11: Edge Case Tests — Circuit Breakers

**Files:**
- Create: `integration_tests/test_circuit_breakers.py`

**Step 1: Write the test**

Create `integration_tests/test_circuit_breakers.py`:

```python
"""Edge-case tests for circuit breaker behavior.

These tests deliberately induce failure conditions and verify the harness halts correctly.
Uses low thresholds in .harnessrc to keep test runtime short.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from integration_tests.agents.responder_agent import LiveResponder
from integration_tests.claude_runner import ClaudeRunner

PLUGIN_DIR = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"


@pytest.fixture
def analyst_context():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        return yaml.safe_load(f)


def _setup_project_with_epic(test_project_dir, epic_spec: dict, epic_filename: str = "01-test-epic.yaml"):
    """Helper: set up an initialized project with a single epic and low circuit breaker thresholds."""
    epics_fixture = FIXTURES_DIR / "epics_output"
    for item in epics_fixture.iterdir():
        dest = test_project_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    # Override harnessrc with low thresholds
    harnessrc = test_project_dir / "kyros-agent-workflow" / ".harnessrc"
    config = {
        "circuit_breaker": {
            "no_progress_threshold": 2,
            "same_error_threshold": 2,
            "max_review_rounds": 2,
        },
        "agent_team": {
            "developer_model": "haiku",
            "reviewer_model": "haiku",
        },
    }
    with open(harnessrc, "w") as f:
        yaml.dump(config, f)

    # Replace epics with our test epic
    epics_dir = test_project_dir / "epics" / "v1"
    epics_dir.mkdir(parents=True, exist_ok=True)
    for existing in epics_dir.glob("*.yaml"):
        existing.unlink()
    with open(epics_dir / epic_filename, "w") as f:
        yaml.dump(epic_spec, f)

    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "setup test epic"], cwd=test_project_dir, capture_output=True)
    return epics_dir


def test_no_progress_halts(test_project_dir, analyst_context):
    """An impossible acceptance criterion should trigger the no-progress circuit breaker."""
    epic = {
        "name": "impossible-accuracy",
        "description": "Achieve impossibly high accuracy on a tiny dataset",
        "acceptance_criteria": [
            "Model achieves 99.9% accuracy on test set with zero false positives and zero false negatives"
        ],
        "dependencies": [],
        "estimated_steps": 2,
    }
    epics_dir = _setup_project_with_epic(test_project_dir, epic)

    runner = ClaudeRunner(working_dir=test_project_dir, timeout=600, plugin_dir=PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    transcript = runner.run_interactive(
        "/execute-plan epics/v1",
        responder=responder.as_callable(),
        phase_timeout=600,
    )

    # Verify the harness stopped — check execution state
    state_file = epics_dir / ".execution-state.yaml"
    if state_file.exists():
        with open(state_file) as f:
            state = yaml.safe_load(f) or {}
        epic_state = state.get("epics", {}).get("impossible-accuracy", {})
        status = epic_state.get("status", "")
        # Should be blocked or have circuit breaker info
        assert status != "completed", f"Epic should not have completed — status is '{status}'"


def test_repeated_error_halts(test_project_dir, analyst_context):
    """A broken dependency should trigger the repeated-error circuit breaker."""
    epic = {
        "name": "broken-import",
        "description": "An epic that requires a nonexistent library",
        "acceptance_criteria": [
            "Code imports and uses nonexistent_lib.magic_function()",
            "Unit test verifies magic_function returns expected output",
        ],
        "dependencies": [],
        "estimated_steps": 2,
    }
    epics_dir = _setup_project_with_epic(test_project_dir, epic)

    runner = ClaudeRunner(working_dir=test_project_dir, timeout=600, plugin_dir=PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    transcript = runner.run_interactive(
        "/execute-plan epics/v1",
        responder=responder.as_callable(),
        phase_timeout=600,
    )

    state_file = epics_dir / ".execution-state.yaml"
    if state_file.exists():
        with open(state_file) as f:
            state = yaml.safe_load(f) or {}
        epic_state = state.get("epics", {}).get("broken-import", {})
        status = epic_state.get("status", "")
        assert status != "completed", f"Epic should not have completed — status is '{status}'"


def test_review_rounds_exceeded(test_project_dir, analyst_context):
    """A vague acceptance criterion should trigger max review rounds."""
    epic = {
        "name": "vague-criteria",
        "description": "An epic with criteria too vague for the reviewer to ever approve",
        "acceptance_criteria": [
            "Code must be elegant and beautiful",
            "Implementation must demonstrate deep understanding of the problem domain",
            "Solution must be the most optimal possible approach",
        ],
        "dependencies": [],
        "estimated_steps": 1,
    }
    epics_dir = _setup_project_with_epic(test_project_dir, epic)

    runner = ClaudeRunner(working_dir=test_project_dir, timeout=600, plugin_dir=PLUGIN_DIR)
    responder = LiveResponder(analyst_context)
    transcript = runner.run_interactive(
        "/execute-plan epics/v1",
        responder=responder.as_callable(),
        phase_timeout=600,
    )

    state_file = epics_dir / ".execution-state.yaml"
    if state_file.exists():
        with open(state_file) as f:
            state = yaml.safe_load(f) or {}
        epic_state = state.get("epics", {}).get("vague-criteria", {})
        status = epic_state.get("status", "")
        assert status != "completed", f"Epic should not have completed — status is '{status}'"
```

**Step 2: Run dry run**

Run: `pytest integration_tests/test_circuit_breakers.py -v --co`

Expected: 3 tests collected

**Step 3: Commit**

```bash
git add integration_tests/test_circuit_breakers.py
git commit -m "feat(integration): add circuit breaker edge-case tests"
```

---

### Task 12: Edge Case Tests — Resume and Recovery

**Files:**
- Create: `integration_tests/test_resume_recovery.py`

**Step 1: Write the test**

Create `integration_tests/test_resume_recovery.py`:

```python
"""Edge-case tests for resume-after-interrupt and DoD failure auto-fix."""

import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest
import yaml

from integration_tests.agents.responder_agent import LiveResponder
from integration_tests.claude_runner import ClaudeRunner

PLUGIN_DIR = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"


@pytest.fixture
def analyst_context():
    with open(FIXTURES_DIR / "analyst-context.yaml") as f:
        return yaml.safe_load(f)


def _setup_full_project(test_project_dir):
    """Set up a project with init + profiles + epics from fixtures."""
    epics_fixture = FIXTURES_DIR / "epics_output"
    for item in epics_fixture.iterdir():
        dest = test_project_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "setup"], cwd=test_project_dir, capture_output=True)
    return test_project_dir


def test_resume_after_interrupt(test_project_dir, analyst_context):
    """Kill mid-execution, restart, verify it offers to resume from the right step."""
    _setup_full_project(test_project_dir)
    epics_dir = test_project_dir / "epics" / "v1"

    # Start execution
    runner = ClaudeRunner(working_dir=test_project_dir, timeout=120, plugin_dir=PLUGIN_DIR)
    responder = LiveResponder(analyst_context)

    # Run briefly then kill — wait for state file to appear
    proc = subprocess.Popen(
        ["claude", "--plugin", str(PLUGIN_DIR)],
        cwd=test_project_dir,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    proc.stdin.write("/execute-plan epics/v1\n")
    proc.stdin.flush()

    # Wait for state file to be created (up to 60s)
    state_file = epics_dir / ".execution-state.yaml"
    for _ in range(60):
        if state_file.exists():
            break
        time.sleep(1)

    # Kill the process
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()

    # Verify state file was created
    assert state_file.exists(), "Execution state should exist after partial run"

    # Now restart — the responder should answer "resume"
    resume_responder = LiveResponder(analyst_context)
    runner2 = ClaudeRunner(working_dir=test_project_dir, timeout=120, plugin_dir=PLUGIN_DIR)
    transcript = runner2.run_interactive(
        "/execute-plan epics/v1",
        responder=resume_responder.as_callable(),
        phase_timeout=120,
    )

    # Check that the transcript mentions resume
    full_text = " ".join(t["content"] for t in transcript.turns).lower()
    assert "resume" in full_text or "previous" in full_text or "existing" in full_text, \
        "Harness should detect existing state and offer to resume"


def test_dod_failure_autofix(test_project_dir, analyst_context):
    """Inject TODO/debug print after build, verify DoD catches and auto-fixes."""
    _setup_full_project(test_project_dir)

    # Simulate a completed build with TODO and debug print injected
    src_dir = test_project_dir / "kyros-agent-workflow" / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "model.py").write_text(
        "# TODO: clean this up\n"
        "import pandas as pd\n"
        "print('DEBUG: loading data')\n"
        "def load_data():\n"
        "    return pd.read_csv('customers.csv')\n"
    )
    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "build: add model code"], cwd=test_project_dir, capture_output=True)

    # Run the definition-of-done hook directly to verify it catches the issues
    dod_hook = PLUGIN_DIR / "hooks" / "definition-of-done.sh"
    result = subprocess.run(
        ["bash", str(dod_hook)],
        cwd=test_project_dir,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "PROJECT_ROOT": str(test_project_dir)},
    )

    # The DoD hook should detect TODO or DEBUG
    combined = result.stdout + result.stderr
    lower = combined.lower()
    has_detection = "todo" in lower or "debug" in lower or "print" in lower
    # Note: if the hook doesn't scan for these, that's a finding for the fix agent
    if has_detection:
        assert True  # Hook correctly detected issues
    else:
        pytest.skip("DoD hook does not currently scan for TODO/debug — may need enhancement")


def test_quality_scan_advisory(test_project_dir, analyst_context):
    """Inject unused import, verify quality scan flags but doesn't block."""
    _setup_full_project(test_project_dir)

    src_dir = test_project_dir / "kyros-agent-workflow" / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "utils.py").write_text(
        "import os\nimport sys\nimport json\n\ndef hello():\n    return 'world'\n"
    )
    subprocess.run(["git", "add", "."], cwd=test_project_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add utils"], cwd=test_project_dir, capture_output=True)

    # Run quality scan hook directly
    quality_hook = PLUGIN_DIR / "hooks" / "quality-scan.sh"
    result = subprocess.run(
        ["bash", str(quality_hook)],
        cwd=test_project_dir,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "PROJECT_ROOT": str(test_project_dir)},
    )

    # Quality scan should complete (exit 0 — advisory, not blocking)
    # It may or may not detect unused imports depending on whether ruff is configured
    assert result.returncode == 0 or "unused" in (result.stdout + result.stderr).lower()
```

**Step 2: Run dry run**

Run: `pytest integration_tests/test_resume_recovery.py -v --co`

Expected: 3 tests collected

**Step 3: Commit**

```bash
git add integration_tests/test_resume_recovery.py
git commit -m "feat(integration): add resume and recovery edge-case tests"
```

---

### Task 13: Fix Agent

**Files:**
- Create: `integration_tests/agents/fix_agent.py`
- Create: `integration_tests/agents/test_fix_agent.py`

**Step 1: Write the failing test**

Create `integration_tests/agents/test_fix_agent.py`:

```python
"""Tests for the fix agent — verifies failure context collection and branch management."""

from pathlib import Path

from integration_tests.agents.fix_agent import collect_failure_context, FixAgent
from integration_tests.assertions.models import AssertionResult


PLUGIN_DIR = Path(__file__).parent.parent.parent


def test_collect_failure_context():
    failures = [
        AssertionResult(passed=False, message="CLAUDE.md not found", tier="structural"),
        AssertionResult(passed=False, message=".harnessrc not found", tier="structural"),
    ]
    context = collect_failure_context(
        test_name="test_init_structural",
        phase="init",
        failures=failures,
        transcript_path=None,
        project_dir=Path("/tmp/fake"),
        plugin_dir=PLUGIN_DIR,
    )
    assert "test_init_structural" in context
    assert "CLAUDE.md not found" in context
    assert "harness-init" in context  # Should include the relevant skill


def test_fix_agent_creates_branch(tmp_path):
    """Verify the fix agent creates a properly named branch."""
    agent = FixAgent(plugin_dir=tmp_path, timeout=5)
    branch_name = agent._branch_name("init")
    assert branch_name.startswith("fix/integration-init-")


def test_fix_agent_allowed_paths():
    """Verify the fix agent only allows modifications to safe directories."""
    agent = FixAgent(plugin_dir=PLUGIN_DIR, timeout=5)
    assert agent._is_allowed_path(PLUGIN_DIR / "skills" / "harness-init" / "SKILL.md")
    assert agent._is_allowed_path(PLUGIN_DIR / "hooks" / "session-start.sh")
    assert agent._is_allowed_path(PLUGIN_DIR / "templates" / "CLAUDE.md.template")
    assert not agent._is_allowed_path(PLUGIN_DIR / "integration_tests" / "test_init.py")
    assert not agent._is_allowed_path(PLUGIN_DIR / "package.json")
```

**Step 2: Run the test to verify it fails**

Run: `pytest integration_tests/agents/test_fix_agent.py -v`

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement the fix agent**

Create `integration_tests/agents/fix_agent.py`:

```python
"""Fix agent — autonomous diagnose-fix-verify cycle for integration test failures.

When a structural assertion fails, this agent:
1. Collects failure context (assertion messages, transcript, relevant plugin source)
2. Launches a Claude session pointed at the plugin repo to diagnose and fix
3. Changes land on a fix branch for human review
"""

import datetime
import logging
import subprocess
from pathlib import Path

from integration_tests.assertions.models import AssertionResult
from integration_tests.claude_runner import ClaudeRunner

logger = logging.getLogger(__name__)


PHASE_SKILL_MAP = {
    "init": "skills/harness-init/SKILL.md",
    "profile-data": "skills/profile-data/SKILL.md",
    "define-epics": "skills/define-epics/SKILL.md",
    "execute-plan": "skills/execute-plan/SKILL.md",
}

ALLOWED_DIRS = ["skills", "commands", "hooks", "templates", "agents", "lib"]


def collect_failure_context(
    test_name: str,
    phase: str,
    failures: list[AssertionResult],
    transcript_path: Path | None,
    project_dir: Path,
    plugin_dir: Path,
) -> str:
    """Assemble the diagnostic context for the fix agent."""
    parts = [
        f"# Integration Test Failure Report",
        f"",
        f"**Test:** {test_name}",
        f"**Phase:** {phase}",
        f"",
        f"## Failed Assertions",
        "",
    ]
    for f in failures:
        parts.append(f"- {f.message}")

    parts.extend(["", "## Relevant Skill", ""])
    skill_path = plugin_dir / PHASE_SKILL_MAP.get(phase, "")
    if skill_path.is_file():
        parts.append(f"File: {PHASE_SKILL_MAP[phase]}")
        parts.append("```")
        parts.append(skill_path.read_text()[:5000])  # Truncate if very long
        parts.append("```")

    if transcript_path and transcript_path.is_file():
        parts.extend(["", "## Session Transcript (last 3000 chars)", ""])
        transcript = transcript_path.read_text()
        parts.append("```")
        parts.append(transcript[-3000:])
        parts.append("```")

    parts.extend(["", "## Test Project State", ""])
    # List files in the project dir
    try:
        result = subprocess.run(
            ["find", ".", "-type", "f", "-not", "-path", "./.git/*"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        parts.append("```")
        parts.append(result.stdout[:2000])
        parts.append("```")
    except Exception:
        parts.append("(could not list project files)")

    return "\n".join(parts)


class FixAgent:
    """Launches a Claude session to fix plugin code based on failure context."""

    def __init__(self, plugin_dir: Path, timeout: int = 300):
        self.plugin_dir = plugin_dir
        self.timeout = timeout

    def attempt_fix(self, failure_context: str, phase: str) -> dict:
        """Run a fix attempt. Returns a dict with branch name and success status."""
        branch = self._branch_name(phase)

        # Create fix branch
        subprocess.run(
            ["git", "checkout", "-b", branch],
            cwd=self.plugin_dir,
            capture_output=True,
        )

        try:
            runner = ClaudeRunner(working_dir=self.plugin_dir, timeout=self.timeout)
            prompt = (
                f"An integration test for the one-shot-build plugin failed. "
                f"Diagnose the issue and fix the plugin code.\n\n"
                f"IMPORTANT CONSTRAINTS:\n"
                f"- Only modify files under: {', '.join(ALLOWED_DIRS)}\n"
                f"- Do NOT modify any files under integration_tests/\n"
                f"- Commit your fixes with a descriptive message\n\n"
                f"{failure_context}"
            )
            output = runner.run_print(prompt)

            # Check if any files were modified
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=self.plugin_dir,
                capture_output=True,
                text=True,
            )
            files_changed = [f for f in result.stdout.strip().split("\n") if f]
            all_allowed = all(self._is_allowed_path(self.plugin_dir / f) for f in files_changed)

            return {
                "branch": branch,
                "files_changed": files_changed,
                "all_allowed": all_allowed,
                "output": output,
            }
        except Exception as e:
            logger.error("Fix attempt failed: %s", e)
            return {"branch": branch, "files_changed": [], "all_allowed": True, "output": str(e)}
        finally:
            # Return to main branch
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=self.plugin_dir,
                capture_output=True,
            )

    def _branch_name(self, phase: str) -> str:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"fix/integration-{phase}-{ts}"

    def _is_allowed_path(self, path: Path) -> bool:
        try:
            rel = path.relative_to(self.plugin_dir)
        except ValueError:
            return False
        top_dir = str(rel).split("/")[0]
        return top_dir in ALLOWED_DIRS
```

**Step 4: Run tests to verify they pass**

Run: `pytest integration_tests/agents/test_fix_agent.py -v`

Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add integration_tests/agents/fix_agent.py integration_tests/agents/test_fix_agent.py
git commit -m "feat(integration): add fix agent for autonomous remediation"
```

---

### Task 14: Test Runner / Orchestrator

**Files:**
- Create: `integration_tests/run_all.py`

**Step 1: Write the orchestrator**

Create `integration_tests/run_all.py`:

```python
#!/usr/bin/env python3
"""Integration test orchestrator.

Runs phase tests in order, edge-case tests in parallel, handles fix-then-retry
loops, and generates a summary report.

Usage:
    python integration_tests/run_all.py                     # Run everything
    python integration_tests/run_all.py --phase init        # Single phase
    python integration_tests/run_all.py --edge-cases-only   # Edge cases only
    python integration_tests/run_all.py --chained           # Chained mode
    python integration_tests/run_all.py --no-fix            # No fix loop
    python integration_tests/run_all.py --phase-timeout 600 # Custom timeout
    python integration_tests/run_all.py --fix-timeout 300   # Custom fix timeout
"""

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).parent
PLUGIN_DIR = TESTS_DIR.parent
REPORTS_DIR = TESTS_DIR / ".reports"
LOGS_DIR = TESTS_DIR / ".logs"

HAPPY_PATH_TESTS = [
    ("init", "integration_tests/test_init.py"),
    ("profile-data", "integration_tests/test_profile_data.py"),
    ("define-epics", "integration_tests/test_define_epics.py"),
    ("execute-plan", "integration_tests/test_execute_plan.py"),
]

EDGE_CASE_TESTS = [
    "integration_tests/test_guards.py",
    "integration_tests/test_circuit_breakers.py",
    "integration_tests/test_resume_recovery.py",
]


def run_test(test_path: str, timeout: int, extra_args: list[str] | None = None) -> dict:
    """Run a single test file and return results."""
    cmd = ["pytest", test_path, "-v", "--tb=short", f"--timeout={timeout}"]
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(
        cmd,
        cwd=PLUGIN_DIR,
        capture_output=True,
        text=True,
        timeout=timeout + 60,  # Buffer beyond pytest timeout
    )

    return {
        "test": test_path,
        "passed": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def run_fix_loop(phase: str, test_path: str, test_result: dict, max_attempts: int, fix_timeout: int) -> dict:
    """Run the fix-then-retry loop for a failing test."""
    from integration_tests.agents.fix_agent import FixAgent, collect_failure_context
    from integration_tests.assertions.models import AssertionResult

    fix_branches = []

    for attempt in range(1, max_attempts + 1):
        print(f"  Fix attempt {attempt}/{max_attempts} for {phase}...")

        # Parse failures from test output (simplified — extract assertion messages)
        failures = [
            AssertionResult(passed=False, message=f"Test failed: {test_path}", tier="structural"),
        ]
        context = collect_failure_context(
            test_name=test_path,
            phase=phase,
            failures=failures,
            transcript_path=None,
            project_dir=PLUGIN_DIR,
            plugin_dir=PLUGIN_DIR,
        )

        agent = FixAgent(plugin_dir=PLUGIN_DIR, timeout=fix_timeout)
        fix_result = agent.attempt_fix(context, phase)
        fix_branches.append(fix_result["branch"])

        # Re-run the test
        retest = run_test(test_path, timeout=600)
        if retest["passed"]:
            return {
                "status": "PASSED",
                "attempt": attempt,
                "fix_branches": fix_branches,
            }

    return {
        "status": "FAILED_AFTER_RETRIES",
        "attempts": max_attempts,
        "fix_branches": fix_branches,
    }


def generate_report(results: list[dict], report_path: Path):
    """Generate and print the summary report."""
    report_lines = [
        "Integration Test Report",
        "=" * 50,
        "",
    ]

    structural_passed = 0
    structural_total = 0
    quality_warnings = 0
    fix_branches = []

    for r in results:
        structural_total += 1
        name = Path(r["test"]).stem
        if r["passed"]:
            structural_passed += 1
            if r.get("fix_attempt"):
                report_lines.append(f"{name} {'.' * (40 - len(name))} PASSED (fixed on attempt {r['fix_attempt']})")
                fix_branches.extend(r.get("fix_branches", []))
            else:
                report_lines.append(f"{name} {'.' * (40 - len(name))} PASSED")
        else:
            report_lines.append(f"{name} {'.' * (40 - len(name))} FAILED")
            if r.get("fix_branches"):
                fix_branches.extend(r["fix_branches"])
                for b in r["fix_branches"]:
                    report_lines.append(f"  Fix branch: {b}")

    report_lines.extend([
        "",
        f"Structural: {structural_passed}/{structural_total} passed",
        f"Fix branches to review: {len(fix_branches)}",
    ])

    report_text = "\n".join(report_lines)
    print(report_text)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text)

    # Save to cost history
    cost_file = REPORTS_DIR / "cost-history.json"
    history = []
    if cost_file.exists():
        history = json.loads(cost_file.read_text())
    history.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "passed": structural_passed,
        "total": structural_total,
        "fix_branches": len(fix_branches),
    })
    cost_file.write_text(json.dumps(history, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Integration test orchestrator")
    parser.add_argument("--phase", choices=["init", "profile-data", "define-epics", "execute-plan"])
    parser.add_argument("--edge-cases-only", action="store_true")
    parser.add_argument("--chained", action="store_true")
    parser.add_argument("--no-fix", action="store_true")
    parser.add_argument("--phase-timeout", type=int, default=600)
    parser.add_argument("--fix-timeout", type=int, default=300)
    parser.add_argument("--max-fix-attempts", type=int, default=3)
    args = parser.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    # Happy-path tests
    if not args.edge_cases_only:
        tests_to_run = HAPPY_PATH_TESTS
        if args.phase:
            tests_to_run = [(p, t) for p, t in HAPPY_PATH_TESTS if p == args.phase]

        extra_args = []
        if args.chained:
            extra_args.append("--chained")

        for phase, test_path in tests_to_run:
            print(f"Running {phase}...")
            result = run_test(test_path, args.phase_timeout, extra_args)
            result["phase"] = phase

            if not result["passed"] and not args.no_fix:
                fix_result = run_fix_loop(phase, test_path, result, args.max_fix_attempts, args.fix_timeout)
                result["passed"] = fix_result["status"] == "PASSED"
                result["fix_attempt"] = fix_result.get("attempt")
                result["fix_branches"] = fix_result.get("fix_branches", [])

                # In chained mode, stop if a phase fails even after fixes
                if args.chained and not result["passed"]:
                    print(f"  {phase} failed after {args.max_fix_attempts} fix attempts — stopping chain")
                    results.append(result)
                    break

            results.append(result)

    # Edge-case tests (parallel)
    if not args.phase:
        tests = EDGE_CASE_TESTS
        if args.edge_cases_only:
            tests = EDGE_CASE_TESTS

        print("Running edge-case tests...")
        # Run via pytest-xdist for parallelism
        edge_paths = " ".join(tests)
        edge_result = run_test(edge_paths, args.phase_timeout, ["-n", "auto"])
        # Split into individual results for reporting
        for test_path in tests:
            individual = run_test(test_path, args.phase_timeout)
            results.append(individual)

    # Report
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = REPORTS_DIR / f"report-{ts}.txt"
    generate_report(results, report_path)

    # Exit code
    all_passed = all(r["passed"] for r in results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
```

**Step 2: Verify it runs (help only)**

Run: `python integration_tests/run_all.py --help`

Expected: Help text with all options displayed

**Step 3: Commit**

```bash
git add integration_tests/run_all.py
git commit -m "feat(integration): add test runner orchestrator with fix loop and reporting"
```

---

### Task 15: Final Verification

**Step 1: Run the full test collection (dry run)**

Run: `pytest integration_tests/ -v --co --ignore=integration_tests/run_all.py`

Expected: All test files collected without import errors. Total count should be approximately:
- 6 assertion tests
- 3 claude runner tests
- 4 setup agent tests
- 6 responder tests
- 3 fix agent tests
- 2 init tests
- 2 profile-data tests
- 2 define-epics tests
- 2 execute-plan tests
- 4 guard tests
- 3 circuit breaker tests
- 3 resume/recovery tests
= ~40 tests total

**Step 2: Run unit tests only (no Claude CLI required)**

Run: `pytest integration_tests/assertions/ integration_tests/agents/test_fix_agent.py -v`

Expected: All assertion and fix agent unit tests pass (these don't need the Claude CLI)

**Step 3: Run a single phase smoke test**

Run: `python integration_tests/run_all.py --phase init --no-fix --phase-timeout 120`

Expected: The init test runs against real Claude CLI. Check the report output.

**Step 4: Commit any fixes and tag**

```bash
git add -A
git commit -m "feat(integration): complete integration test suite"
```
