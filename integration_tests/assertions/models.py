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
