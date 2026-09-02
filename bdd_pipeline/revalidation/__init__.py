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

from bdd_pipeline.revalidation.cli import main
from bdd_pipeline.revalidation.discovery import (
    DiscoveredProblem,
    discover_problems,
)
from bdd_pipeline.revalidation.previous_results import load_failed_ids
from bdd_pipeline.revalidation.promotion import move_to_validated
from bdd_pipeline.revalidation.runner import run_revalidation

__all__ = [
    "main",
    "run_revalidation",
    "discover_problems",
    "DiscoveredProblem",
    "load_failed_ids",
    "move_to_validated",
]