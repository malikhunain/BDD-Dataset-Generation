"""
Parsing utilities for Behave console output.

These parsers convert Behave's plain-format output into a structured
ValidationResult.
"""

import re

from validation.models import ValidationResult


_SCENARIO_SUMMARY_RE = re.compile(
    r"(\d+) scenarios? passed,\s*(\d+) failed"
)

_STEP_SUMMARY_RE = re.compile(
    r"(\d+) steps? passed,\s*(\d+) failed"
)

_FAILING_SCENARIOS_RE = re.compile(
    r"Failing scenarios:\s*(.*?)(?:\n\n|\Z)",
    re.DOTALL,
)


def extract_first_error(output: str) -> str:
    """
    Extract the first error-like line from Behave output.

    Falls back to the last 300 characters if no explicit error line is found.
    """
    for line in output.splitlines():
        line = line.strip()

        if any(
            keyword in line
            for keyword in (
                "Error",
                "error",
                "ASSERT",
                "assert",
                "Traceback",
            )
        ):
            return line[:200]

    return output[-300:].strip()


def parse_behave_output(output: str, returncode: int) -> ValidationResult:
    """
    Parse Behave's plain-format output into a ValidationResult.

    Behave plain output usually ends with summary lines such as:

        1 feature passed, 0 failed, 0 skipped
        5 scenarios passed, 0 failed, 0 skipped
        15 steps passed, 0 failed, 0 skipped
    """
    result = ValidationResult(
        status="PASS" if returncode == 0 else "FAIL_BEHAVE",
        behave_output=output,
    )

    scenario_match = _SCENARIO_SUMMARY_RE.search(output)
    if scenario_match:
        result.scenarios_passed = int(scenario_match.group(1))
        result.scenarios_failed = int(scenario_match.group(2))
        result.scenarios_total = (
            result.scenarios_passed + result.scenarios_failed
        )

    step_match = _STEP_SUMMARY_RE.search(output)
    if step_match:
        result.steps_passed = int(step_match.group(1))
        result.steps_failed = int(step_match.group(2))
        result.steps_total = result.steps_passed + result.steps_failed

    failing = _FAILING_SCENARIOS_RE.findall(output)
    if failing:
        result.failing_scenarios = [
            line.strip()
            for line in failing[0].strip().splitlines()
            if line.strip()
        ]

    if "ImportError" in output or "ModuleNotFoundError" in output:
        result.status = "FAIL_SYNTAX"
        result.error_message = extract_first_error(output)

    elif "AttributeError" in output and "has no attribute" in output:
        result.status = "FAIL_SYNTAX"
        result.error_message = extract_first_error(output)

    elif "undefined" in output.lower() and result.scenarios_total == 0:
        result.status = "FAIL_SYNTAX"
        result.error_message = (
            "Behave could not match step definitions (undefined steps)"
        )

    elif returncode != 0 and not result.error_message:
        result.error_message = (
            extract_first_error(output) or "Behave exited non-zero"
        )

    return result


# Backward-compatible aliases for older private names.
_parse_behave_output = parse_behave_output
_extract_first_error = extract_first_error