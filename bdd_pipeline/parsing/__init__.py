"""
Parsing package for the BDD dataset generation pipeline.

Currently this package wraps the legacy output parser. The parser is kept in
legacy_parser.py until it is split into extraction, fixing, validation, and
file-writing modules with golden tests.
"""

from bdd_pipeline.parsing.models import (
    ParsedOutput,
    ParseError
)
from bdd_pipeline.parsing.writer import (
    parse_and_write,
    count_scenarios,
    _problem_dir
)

__all__ = [
    "ParsedOutput",
    "ParseError",
    "parse_and_write",
    "count_scenarios",
    "_problem_dir"
]