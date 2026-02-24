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
