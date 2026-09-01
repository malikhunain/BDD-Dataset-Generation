"""
Compatibility wrapper for output parsing.
"""

from parsing.models import (
    ParsedOutput,
    ParseError
)
from parsing.writer import (
    parse_and_write,
    count_scenarios
)

__all__ = [
    "ParsedOutput",
    "ParseError",
    "parse_and_write",
    "count_scenarios",
]