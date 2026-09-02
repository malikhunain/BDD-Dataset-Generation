"""
Compatibility entry point for revalidation.

Use this to:
  - Validate everything in generated/ and promote passing ones
  - Re-test after manually fixing a step definitions file
  - Check which problems pass/fail after an edit
  - Target a specific subset by problem ID or dataset source

Usage:
    # Validate everything → move passing ones to validated_dataset/
    python revalidate.py

    # Only HumanEval problems
    python revalidate.py --source HumanEval

    # Only MBPP problems
    python revalidate.py --source MBPP

    # Only specific problems (space-separated, underscore or slash format)
    python revalidate.py --ids HumanEval_0 HumanEval_2 MBPP_602

    # Only problems that previously FAILED (reads existing results.csv)
    python revalidate.py --failed-only

    # Verbose: print full Behave output for every failure
    python revalidate.py --verbose

    # Validate only — do NOT move passing problems (dry-run style)
    python revalidate.py --no-move
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bdd_pipeline.revalidation import (
    DiscoveredProblem,
    discover_problems,
    load_failed_ids,
    main,
    move_to_validated,
    run_revalidation,
)

__all__ = [
    "main",
    "run_revalidation",
    "discover_problems",
    "DiscoveredProblem",
    "load_failed_ids",
    "move_to_validated",
]


if __name__ == "__main__":
    main()