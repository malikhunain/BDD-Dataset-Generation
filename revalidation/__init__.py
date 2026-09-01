"""
Revalidation package.

This package re-runs validation on already-generated problems and optionally
promotes passing problems into validated_dataset/.

Use this to:
  - Validate everything in generated/ and promote passing ones
  - Re-test after manually fixing a step definitions file
  - Check which problems pass/fail after an edit
  - Target a specific subset by problem ID or dataset source
"""

from revalidation.cli import main
from revalidation.discovery import (
    DiscoveredProblem,
    discover_problems,
)
from revalidation.previous_results import load_failed_ids
from revalidation.promotion import move_to_validated
from revalidation.runner import run_revalidation

__all__ = [
    "main",
    "run_revalidation",
    "discover_problems",
    "DiscoveredProblem",
    "load_failed_ids",
    "move_to_validated",
]