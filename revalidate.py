"""
revalidate.py — Re-run Behave on all (or selected) already-generated problems.
               Passing problems are automatically moved to validated_dataset/.

Use this when you want to:
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

import argparse
import csv
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import GENERATED_DIR, RESULTS_DIR, VALIDATED_DATASET_DIR, BEHAVE_TIMEOUT
from output_parser import ParsedOutput
from validator import validate, ValidationResult


# ── Problem discovery ────────────────────────────────────────────────────────

def discover_problems(generated_dir: Path) -> list[dict]:
    """
    Walk generated/ and find every valid problem directory.
    A valid problem dir contains:
      - solution.py
      - features/*.feature
      - features/steps/*_steps.py
    """
    problems = []

    for problem_dir in sorted(generated_dir.iterdir()):
        if not problem_dir.is_dir():
            continue

        solution_path = problem_dir / "solution.py"
        features_dir  = problem_dir / "features"
        steps_dir     = features_dir / "steps"

        if not solution_path.exists():
            continue

        feature_files = list(features_dir.glob("*.feature")) if features_dir.exists() else []
        steps_files   = list(steps_dir.glob("*_steps.py"))   if steps_dir.exists() else []

        if not feature_files or not steps_files:
            continue

        # "HumanEval_0" → "HumanEval/0"
        raw_id     = problem_dir.name
        problem_id = raw_id.replace("_", "/", 1)
        source     = problem_id.split("/")[0]

        problems.append({
            "problem_id":    problem_id,
            "raw_id":        raw_id,
            "source":        source,
            "problem_dir":   problem_dir,        # ← full Path to the directory
            "feature_path":  feature_files[0],
            "steps_path":    steps_files[0],
            "solution_path": solution_path,
        })

    return problems


# ── Load previous results ────────────────────────────────────────────────────

def load_failed_ids(results_csv: Path) -> set[str]:
    """Read results.csv and return the set of problem_ids that did not PASS."""
    if not results_csv.exists():
        print(f"[revalidate] No existing results.csv at {results_csv}")
        return set()

    failed = set()
    with open(results_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status", "") != "PASS":
                failed.add(row["problem_id"])
    return failed


# ── Move to validated_dataset ────────────────────────────────────────────────

def move_to_validated(problem_dir: Path) -> bool:
    """
    Move a problem directory from generated/ to validated_dataset/.
    If a copy already exists in validated_dataset/, it is replaced.
    Returns True on success, False on error.
    """
    VALIDATED_DATASET_DIR.mkdir(parents=True, exist_ok=True)
    dest = VALIDATED_DATASET_DIR / problem_dir.name

    try:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(problem_dir), str(dest))
        return True
    except Exception as e:
        print(f"         [MOVE ERROR] Could not move {problem_dir.name}: {e}")
        return False


# ── Main ─────────────────────────────────────────────────────────────────────

def run_revalidation(
    source:      str  = None,
    ids:         list = None,
    failed_only: bool = False,
    verbose:     bool = False,
    no_move:     bool = False,
):
    generated_dir = Path(GENERATED_DIR)
    results_dir   = Path(RESULTS_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)

    if not generated_dir.exists():
        print(f"ERROR: generated/ directory not found at {generated_dir}")
        sys.exit(1)

    # ── Discover ─────────────────────────────────────────────────────────────
    all_problems = discover_problems(generated_dir)
    if not all_problems:
        print("No valid problem directories found in generated/")
        sys.exit(1)

    print(f"Found {len(all_problems)} problem directories in generated/")

    if not no_move:
        print(f"Passing problems will be moved to: {VALIDATED_DATASET_DIR}")
    else:
        print("--no-move: passing problems will NOT be moved.")

    # ── Apply filters ─────────────────────────────────────────────────────────
    problems = all_problems

    if source:
        problems = [p for p in problems if p["source"] == source]
        print(f"Filtered to source='{source}': {len(problems)} problems")

    if ids:
        normalised_ids = {i.replace("/", "_") for i in ids}
        problems = [p for p in problems if p["raw_id"] in normalised_ids]
        print(f"Filtered to {len(ids)} specific IDs: {len(problems)} found")

    if failed_only:
        results_csv = results_dir / "results.csv"
        failed_ids  = load_failed_ids(results_csv)
        if not failed_ids:
            print("No failed problems in results.csv — running all")
        else:
            problems = [p for p in problems if p["problem_id"] in failed_ids]
            print(f"Filtered to previously failed: {len(problems)} problems")

    if not problems:
        print("No problems match the given filters.")
        sys.exit(0)

    # ── Run Behave on each ────────────────────────────────────────────────────
    print(f"\nRe-validating {len(problems)} problems...\n")

    output_csv = results_dir / "revalidate_results.csv"
    csv_file   = open(output_csv, "w", newline="", encoding="utf-8")
    csv_writer = csv.DictWriter(csv_file, fieldnames=[
        "problem_id", "source", "status",
        "scenarios_passed", "scenarios_total",
        "steps_passed", "steps_total",
        "scenario_pass_rate", "elapsed_s",
        "moved_to_validated", "error_message",
    ])
    csv_writer.writeheader()

    n_pass = n_fail = n_error = n_moved = 0
    total_start = time.time()

    for i, prob in enumerate(problems, 1):
        t0 = time.time()

        parsed = ParsedOutput(
            feature_content = prob["feature_path"].read_text(encoding="utf-8"),
            steps_content   = prob["steps_path"].read_text(encoding="utf-8"),
            feature_path    = prob["feature_path"],
            steps_path      = prob["steps_path"],
            solution_path   = prob["solution_path"],
        )

        result: ValidationResult = validate(parsed)
        elapsed = time.time() - t0
        moved   = False

        # ── Print result line ─────────────────────────────────────────────────
        icon = "✓" if result.status == "PASS" else "✗"
        print(
            f"  [{i:>3}/{len(problems)}] {icon} {prob['problem_id']:<30} "
            f"{result.scenarios_passed}/{result.scenarios_total} scenarios  "
            f"({elapsed:.1f}s)",
            end="",
        )

        if result.status == "PASS":
            n_pass += 1

            # ── Move to validated_dataset/ ────────────────────────────────────
            if not no_move:
                moved = move_to_validated(prob["problem_dir"])
                if moved:
                    n_moved += 1
                    print(f"  → moved to validated_dataset/")
                else:
                    print(f"  → MOVE FAILED (see error above)")
            else:
                print()  # newline

        else:
            print()  # newline for the status line
            print(f"         {result.status}: {result.error_message[:120]}")
            if verbose and result.behave_output:
                print("         --- Behave output ---")
                for line in result.behave_output.splitlines()[-20:]:
                    print(f"         {line}")
                print("         ---------------------")

            if result.status in ("FAIL_BEHAVE", "FAIL_SYNTAX"):
                n_fail += 1
            else:
                n_error += 1

        # ── CSV row ───────────────────────────────────────────────────────────
        csv_writer.writerow({
            "problem_id":          prob["problem_id"],
            "source":              prob["source"],
            "status":              result.status,
            "scenarios_passed":    result.scenarios_passed,
            "scenarios_total":     result.scenarios_total,
            "steps_passed":        result.steps_passed,
            "steps_total":         result.steps_total,
            "scenario_pass_rate":  f"{result.pass_rate:.3f}",
            "elapsed_s":           f"{elapsed:.1f}",
            "moved_to_validated":  moved,
            "error_message":       result.error_message[:200],
        })
        csv_file.flush()

    csv_file.close()
    total_elapsed = time.time() - total_start
    total = len(problems)
    pass_pct = n_pass / total * 100 if total else 0

    # ── Summary ───────────────────────────────────────────────────────────────
    move_line = (
        f"Moved to validated : {n_moved}"
        if not no_move
        else "Move               : disabled (--no-move)"
    )

    print(f"""
{'='*55}
RE-VALIDATION SUMMARY
{'='*55}
Total problems     : {total}
PASS               : {n_pass}  ({pass_pct:.1f}%)
FAIL               : {n_fail}
ERROR/TIMEOUT      : {n_error}
{move_line}
Total elapsed      : {total_elapsed:.0f}s
Results CSV        : {output_csv}
Validated dataset  : {VALIDATED_DATASET_DIR}
{'='*55}""")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Re-run Behave on generated problems. "
            "Passing problems are automatically moved to validated_dataset/."
        )
    )
    parser.add_argument(
        "--source", choices=["HumanEval", "MBPP"],
        help="Only validate problems from this dataset"
    )
    parser.add_argument(
        "--ids", nargs="+", metavar="PROBLEM_ID",
        help="Specific problem IDs to validate (e.g. HumanEval_0 MBPP_602)"
    )
    parser.add_argument(
        "--failed-only", action="store_true",
        help="Only re-validate problems that failed in the last results.csv"
    )
    parser.add_argument(
        "--no-move", action="store_true",
        help="Validate but do NOT move passing problems to validated_dataset/"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print full Behave output for each failure"
    )
    args = parser.parse_args()

    run_revalidation(
        source=args.source,
        ids=args.ids,
        failed_only=args.failed_only,
        verbose=args.verbose,
        no_move=args.no_move,
    )


if __name__ == "__main__":
    main()