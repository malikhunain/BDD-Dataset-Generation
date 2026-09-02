"""
Command-line interface for revalidation.
"""

import argparse
from bdd_pipeline.revalidation.runner import run_revalidation


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Re-run Behave on generated problems. "
            "Passing problems are automatically moved to validated_dataset/."
        )
    )

    parser.add_argument(
        "--source",
        choices=["HumanEval", "MBPP"],
        help="Only validate problems from this dataset",
    )

    parser.add_argument(
        "--ids",
        nargs="+",
        metavar="PROBLEM_ID",
        help="Specific problem IDs to validate, e.g. HumanEval_0 MBPP_602",
    )

    parser.add_argument(
        "--failed-only",
        action="store_true",
        help="Only re-validate problems that failed in the last results.csv",
    )

    parser.add_argument(
        "--no-move",
        action="store_true",
        help="Validate but do NOT move passing problems to validated_dataset/",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print full Behave output for each failure",
    )

    args = parser.parse_args()

    run_revalidation(
        source=args.source,
        ids=args.ids,
        failed_only=args.failed_only,
        verbose=args.verbose,
        no_move=args.no_move,
    )