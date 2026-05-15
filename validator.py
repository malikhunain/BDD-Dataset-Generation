"""
validator.py — Runs Behave against the reference solution and parses the results.

This is the quality gate: a generated entry is only accepted if Behave
passes all scenarios against the known-correct reference solution.
"""

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from config import BEHAVE_TIMEOUT
from output_parser import ParsedOutput


@dataclass
class ValidationResult:
    status:           str           # "PASS" | "FAIL_BEHAVE" | "FAIL_SYNTAX" | "FAIL_TIMEOUT"
    scenarios_passed: int  = 0
    scenarios_failed: int  = 0
    scenarios_total:  int  = 0
    steps_passed:     int  = 0
    steps_failed:     int  = 0
    steps_total:      int  = 0
    error_message:    str  = ""
    behave_output:    str  = ""
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


# ── Behave runner ────────────────────────────────────────────────────────────

def validate(parsed: ParsedOutput) -> ValidationResult:
    """
    Run Behave on the generated feature file using the reference solution.
    Returns a ValidationResult describing scenario-level pass/fail.
    """
    features_dir = parsed.feature_path.parent

    cmd = [
        sys.executable, "-m", "behave",
        "--no-capture",
        "--format", "plain",
        f"-D", f"solution_path={parsed.solution_path}",
        str(features_dir),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=BEHAVE_TIMEOUT,
            cwd=str(features_dir.parent),   # project root = problem dir
        )
        output = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return ValidationResult(
            status="FAIL_TIMEOUT",
            error_message=f"Behave timed out after {BEHAVE_TIMEOUT}s",
        )
    except Exception as e:
        return ValidationResult(
            status="FAIL_SYNTAX",
            error_message=f"Could not run Behave: {e}",
        )

    return _parse_behave_output(output, proc.returncode)


# ── Output parser ────────────────────────────────────────────────────────────

def _parse_behave_output(output: str, returncode: int) -> ValidationResult:
    """
    Parse Behave's plain-format output into a ValidationResult.

    Behave plain output ends with a summary line like:
      1 feature passed, 0 failed, 0 skipped
      5 scenarios passed, 0 failed, 0 skipped
      15 steps passed, 0 failed, 0 skipped
    """
    result = ValidationResult(
        status="PASS" if returncode == 0 else "FAIL_BEHAVE",
        behave_output=output,
    )

    # Parse scenario summary — handles both "1 scenario passed" and "2 scenarios passed"
    # and optional "N error," field in the summary line
    sc_match = re.search(
        r"(\d+) scenarios? passed,\s*(\d+) failed",
        output,
    )
    if sc_match:
        result.scenarios_passed = int(sc_match.group(1))
        result.scenarios_failed = int(sc_match.group(2))
        result.scenarios_total  = result.scenarios_passed + result.scenarios_failed

    # Parse step summary
    st_match = re.search(
        r"(\d+) steps? passed,\s*(\d+) failed",
        output,
    )
    if st_match:
        result.steps_passed = int(st_match.group(1))
        result.steps_failed = int(st_match.group(2))
        result.steps_total  = result.steps_passed + result.steps_failed

    # Collect names of failing scenarios for error_message
    failing = re.findall(r"Failing scenarios:\s*(.*?)(?:\n\n|\Z)", output, re.DOTALL)
    if failing:
        result.failing_scenarios = [
            line.strip() for line in failing[0].strip().splitlines() if line.strip()
        ]

    # If Behave errored with undefined steps or import errors, note it
    if "ImportError" in output or "ModuleNotFoundError" in output:
        result.status = "FAIL_SYNTAX"
        result.error_message = _extract_first_error(output)
    elif "AttributeError" in output and "has no attribute" in output:
        # Wrong function name in steps
        result.status = "FAIL_SYNTAX"
        result.error_message = _extract_first_error(output)
    elif "undefined" in output.lower() and result.scenarios_total == 0:
        result.status = "FAIL_SYNTAX"
        result.error_message = "Behave could not match step definitions (undefined steps)"
    elif returncode != 0 and not result.error_message:
        result.error_message = _extract_first_error(output) or "Behave exited non-zero"

    return result


def _extract_first_error(output: str) -> str:
    """Extract the first error/traceback line from Behave output."""
    for line in output.splitlines():
        line = line.strip()
        if any(k in line for k in ("Error", "error", "ASSERT", "assert", "Traceback")):
            return line[:200]
    return output[-300:].strip()