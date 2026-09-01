"""
Behave execution for generated BDD problems.
"""

from __future__ import annotations
import subprocess
import sys
from typing import TYPE_CHECKING
from config import BEHAVE_TIMEOUT
from validation.models import ValidationResult
from validation.output_parsing import parse_behave_output


if TYPE_CHECKING:
    from output_parser import ParsedOutput


def validate(parsed: ParsedOutput) -> ValidationResult:
    """
    Run Behave on the generated feature file using the reference solution.

    Returns a ValidationResult describing scenario-level and step-level
    pass/fail behavior.
    """
    features_dir = parsed.feature_path.parent

    cmd = [
        sys.executable,
        "-m",
        "behave",
        "--no-capture",
        "--format",
        "plain",
        "-D",
        f"solution_path={parsed.solution_path}",
        str(features_dir),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=BEHAVE_TIMEOUT,
            cwd=str(features_dir.parent),
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

    return parse_behave_output(output, proc.returncode)