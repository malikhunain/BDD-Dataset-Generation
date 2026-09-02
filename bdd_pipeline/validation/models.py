"""
Validation result model.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ValidationResult:
    """
    Result of validating one generated BDD problem with Behave.

    Status values:
        PASS
        FAIL_BEHAVE
        FAIL_SYNTAX
        FAIL_TIMEOUT
    """

    status: str
    scenarios_passed: int = 0
    scenarios_failed: int = 0
    scenarios_total: int = 0
    steps_passed: int = 0
    steps_failed: int = 0
    steps_total: int = 0
    error_message: str = ""
    behave_output: str = ""
    failing_scenarios: List[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.scenarios_total == 0:
            return 0.0
        return self.scenarios_passed / self.scenarios_total

    @property
    def step_pass_rate(self) -> float:
        if self.steps_total == 0:
            return 0.0
        return self.steps_passed / self.steps_total