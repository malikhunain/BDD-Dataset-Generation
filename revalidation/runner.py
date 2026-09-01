"""
Revalidation runner.

This module re-runs Behave validation on already-generated problems using the
shared validation component. It does not implement Behave execution itself.
"""

import csv
import sys
import time
from pathlib import Path
from typing import List, Optional
from config import GENERATED_DIR, RESULTS_DIR, VALIDATED_DATASET_DIR
from output_parser import ParsedOutput
from revalidation.previous_results import load_failed_ids
from revalidation.promotion import move_to_validated
from validation import ValidationResult, validate
from revalidation.discovery import (
    DiscoveredProblem,
    discover_problems,
)


REVALIDATE_CSV_FIELDNAMES = [
    "problem_id",
    "source",
    "status",
    "scenarios_passed",
    "scenarios_total",
    "steps_passed",
    "steps_total",
    "scenario_pass_rate",
    "elapsed_s",
    "moved_to_validated",
    "error_message",
]


def run_revalidation(
    source: Optional[str] = None,
    ids: Optional[List[str]] = None,
    failed_only: bool = False,
    verbose: bool = False,
    no_move: bool = False,
) -> None:
    """
    Re-validate generated problems and optionally move passing problems to validated_dataset/.
    """
    generated_dir = Path(GENERATED_DIR)
    results_dir = Path(RESULTS_DIR)

    results_dir.mkdir(parents=True, exist_ok=True)

    if not generated_dir.exists():
        print(f"ERROR: generated/ directory not found at {generated_dir}")
        sys.exit(1)

    all_problems = discover_problems(generated_dir)

    if not all_problems:
        print("No valid problem directories found in generated/")
        sys.exit(1)

    print(f"Found {len(all_problems)} problem directories in generated/")

    if not no_move:
        print(f"Passing problems will be moved to: {VALIDATED_DATASET_DIR}")
    else:
        print("--no-move: passing problems will NOT be moved.")

    problems = all_problems

    if source:
        problems = [
            problem
            for problem in problems
            if problem.source == source
        ]
        print(f"Filtered to source='{source}': {len(problems)} problems")

    if ids:
        normalised_ids = {
            problem_id.replace("/", "_")
            for problem_id in ids
        }

        problems = [
            problem
            for problem in problems
            if problem.raw_id in normalised_ids
        ]

        print(
            f"Filtered to {len(ids)} specific IDs: "
            f"{len(problems)} found"
        )

    if failed_only:
        results_csv = results_dir / "results.csv"
        failed_ids = load_failed_ids(results_csv)

        if not failed_ids:
            print("No failed problems in results.csv — running all")
        else:
            problems = [
                problem
                for problem in problems
                if problem.problem_id in failed_ids
            ]
            print(
                f"Filtered to previously failed: "
                f"{len(problems)} problems"
            )

    if not problems:
        print("No problems match the given filters.")
        sys.exit(0)

    print(f"\nRe-validating {len(problems)} problems...\n")

    output_csv = results_dir / "revalidate_results.csv"

    csv_file = open(output_csv, "w", newline="", encoding="utf-8")
    csv_writer = csv.DictWriter(
        csv_file,
        fieldnames=REVALIDATE_CSV_FIELDNAMES,
    )
    csv_writer.writeheader()

    n_pass = 0
    n_fail = 0
    n_error = 0
    n_moved = 0

    total_start = time.time()

    for index, problem in enumerate(problems, 1):
        start_time = time.time()

        parsed = ParsedOutput(
            feature_content=problem.feature_path.read_text(encoding="utf-8"),
            steps_content=problem.steps_path.read_text(encoding="utf-8"),
            feature_path=problem.feature_path,
            steps_path=problem.steps_path,
            solution_path=problem.solution_path,
        )

        result: ValidationResult = validate(parsed)
        elapsed = time.time() - start_time

        moved = False

        icon = "✓" if result.status == "PASS" else "✗"

        print(
            f"  [{index:>3}/{len(problems)}] {icon} {problem.problem_id:<30} "
            f"{result.scenarios_passed}/{result.scenarios_total} scenarios  "
            f"({elapsed:.1f}s)",
            end="",
        )

        if result.status == "PASS":
            n_pass += 1

            if not no_move:
                moved = move_to_validated(problem.problem_dir)

                if moved:
                    n_moved += 1
                    print("  → moved to validated_dataset/")
                else:
                    print("  → MOVE FAILED (see error above)")
            else:
                print()

        else:
            print()
            print(
                f"         {result.status}: "
                f"{result.error_message[:120]}"
            )

            if verbose and result.behave_output:
                print("         --- Behave output ---")

                for line in result.behave_output.splitlines()[-20:]:
                    print(f"         {line}")

                print("         ---------------------")

            if result.status in ("FAIL_BEHAVE", "FAIL_SYNTAX"):
                n_fail += 1
            else:
                n_error += 1

        csv_writer.writerow(
            {
                "problem_id": problem.problem_id,
                "source": problem.source,
                "status": result.status,
                "scenarios_passed": result.scenarios_passed,
                "scenarios_total": result.scenarios_total,
                "steps_passed": result.steps_passed,
                "steps_total": result.steps_total,
                "scenario_pass_rate": f"{result.pass_rate:.3f}",
                "elapsed_s": f"{elapsed:.1f}",
                "moved_to_validated": moved,
                "error_message": result.error_message[:200],
            }
        )

        csv_file.flush()

    csv_file.close()

    total_elapsed = time.time() - total_start
    total = len(problems)
    pass_percentage = n_pass / total * 100 if total else 0

    move_line = (
        f"Moved to validated : {n_moved}"
        if not no_move
        else "Move               : disabled (--no-move)"
    )

    print(
        f"""
{'=' * 55}
RE-VALIDATION SUMMARY
{'=' * 55}
Total problems     : {total}
PASS               : {n_pass}  ({pass_percentage:.1f}%)
FAIL               : {n_fail}
ERROR/TIMEOUT      : {n_error}
{move_line}
Total elapsed      : {total_elapsed:.0f}s
Results CSV        : {output_csv}
Validated dataset  : {VALIDATED_DATASET_DIR}
{'=' * 55}"""
    )