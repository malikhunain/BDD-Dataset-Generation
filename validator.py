"""
Compatibility wrapper for validation.
"""

from validation import (
    ValidationResult,
    validate,
)
from validation.output_parsing import (
    extract_first_error as _extract_first_error,
    parse_behave_output as _parse_behave_output,
)

__all__ = [
    "ValidationResult",
    "validate",
    "_extract_first_error",
    "_parse_behave_output",
]