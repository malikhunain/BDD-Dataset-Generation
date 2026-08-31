"""
data_loader.py — Load HumanEval and MBPP problems from local JSONL files.

Both datasets are normalised into a common ProblemRecord dataclass so the
rest of the pipeline doesn't need to know which dataset a problem came from.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from config import HUMANEVAL_JSONL, MBPP_JSONL, HUMANEVAL_LIMIT, MBPP_LIMIT, NEW_DATASET_JSONL, NEW_DATASET_LIMIT

# Functions with these names are not valid standalone algorithmic problems
_SKIP_FUNCTION_NAMES = frozenset({
    "__init__", "__str__", "__repr__", "__eq__", "__hash__",
    "__len__", "__iter__", "__next__", "main",
})


@dataclass
class ProblemRecord:
    """Normalised representation of a single coding problem."""
    problem_id:          str
    source:              str
    function_name:       str
    nl_description:      str
    function_signature:  str
    docstring_examples:  List[str]
    reference_solution:  str
    existing_tests:      List[str]
    raw:                 dict = field(default_factory=dict, repr=False)


# HumanEval
def _extract_assert_lines(test_code: str, fn_name: str) -> List[str]:
    lines = []
    for line in test_code.splitlines():
        stripped = line.strip()
        if stripped.startswith("assert"):
            lines.append(stripped.replace("candidate(", f"{fn_name}("))
    return lines[:8]


def _parse_humaneval_row(row: dict) -> Optional[ProblemRecord]:
    try:
        task_id  = row["task_id"]
        prompt   = row["prompt"]
        solution = row["canonical_solution"]
        entry    = row["entry_point"]
        test_raw = row.get("test", "")

        doc_match = re.search(r'"""(.*?)"""', prompt, re.DOTALL)
        docstring = doc_match.group(1).strip() if doc_match else ""

        examples = [
            line.strip()
            for line in docstring.splitlines()
            if ">>>" in line or line.strip().startswith("#")
        ]

        desc_lines = []
        for line in docstring.splitlines():
            if ">>>" in line:
                break
            if line.strip():
                desc_lines.append(line.strip())
        nl_description = " ".join(desc_lines) if desc_lines else docstring[:200]

        sig_match = re.search(r"(def\s+\w+\s*\(.*?\)\s*(?:->\s*\S+)?\s*):", prompt)
        signature = (sig_match.group(0) + ":").strip() if sig_match else f"def {entry}(...):"

        reference      = prompt + solution
        existing_tests = _extract_assert_lines(test_raw, entry)

        return ProblemRecord(
            problem_id=task_id,
            source="HumanEval",
            function_name=entry,
            nl_description=nl_description,
            function_signature=signature,
            docstring_examples=examples,
            reference_solution=reference,
            existing_tests=existing_tests,
            raw=row,
        )
    except Exception as e:
        print(f"  [data_loader] Failed to parse HumanEval row {row.get('task_id')}: {e}")
        return None


# MBPP
def _parse_mbpp_row(row: dict, index: int, verbose: bool = False) -> Optional[ProblemRecord]:
    """
    Parse one MBPP row. Returns None (with a printed reason) if the row
    is not a valid standalone algorithmic problem.

    MBPP has 974 rows across multiple splits. Many rows are skipped because:
      - The 'full' split rows use a different schema (no 'code' field, or
        code is a class body rather than a standalone function)
      - Some rows define classes rather than functions
      - Some rows have empty or placeholder code
    """
    task_id = f"MBPP/{row.get('task_id', index)}"

    try:
        text      = row.get("text", "").strip()
        code      = row.get("code", "").strip()
        test_list = row.get("test_list", [])

        # Guard: empty code
        if not code:
            if verbose:
                print(f"  [data_loader] Skipping {task_id}: empty 'code' field")
            return None

        # Guard: no function definition
        fn_match = re.search(r"def\s+(\w+)\s*\(", code)
        if not fn_match:
            if verbose:
                print(f"  [data_loader] Skipping {task_id}: no 'def' found in code")
            return None

        fn_name = fn_match.group(1)

        # Guard: non-algorithmic function names
        if fn_name in _SKIP_FUNCTION_NAMES or fn_name.startswith("__"):
            print(f"  [data_loader] Skipping {task_id}: '{fn_name}' is not a valid algorithmic function")
            return None

        # Guard: empty description
        if not text:
            if verbose:
                print(f"  [data_loader] Skipping {task_id}: empty 'text' field")
            return None

        # Guard: empty test_list
        # Problems without test assertions cannot be validated by Behave
        clean_tests = [t.strip() for t in test_list if t.strip()]
        if not clean_tests:
            if verbose:
                print(f"  [data_loader] Skipping {task_id}: no test assertions in 'test_list'")
            return None

        sig_match = re.search(r"(def\s+\w+\s*\(.*?\)\s*(?:->\s*\S+)?\s*):", code)
        signature = (sig_match.group(0) + ":").strip() if sig_match else f"def {fn_name}(...):"

        return ProblemRecord(
            problem_id=task_id,
            source="MBPP",
            function_name=fn_name,
            nl_description=text,
            function_signature=signature,
            docstring_examples=clean_tests,
            reference_solution=code,
            existing_tests=clean_tests,
            raw=row,
        )

    except Exception as e:
        print(f"  [data_loader] Failed to parse {task_id}: {e}")
        return None


# Loaders
def load_humaneval(limit: int = HUMANEVAL_LIMIT) -> List[ProblemRecord]:
    path = Path(HUMANEVAL_JSONL)
    if not path.exists():
        raise FileNotFoundError(
            f"HumanEval data not found at {path}\n"
            "See README.md for download instructions."
        )
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if len(records) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            rec = _parse_humaneval_row(json.loads(line))
            if rec:
                records.append(rec)
    print(f"[data_loader] Loaded {len(records)} HumanEval problems")
    return records


def load_mbpp(limit: int = MBPP_LIMIT, verbose: bool = False) -> List[ProblemRecord]:
    """
    Load MBPP problems from the JSONL file.

    Pass verbose=True to print the reason for every skipped row —
    useful for understanding why the loaded count is lower than the file row count.
    """
    path = Path(MBPP_JSONL)
    if not path.exists():
        raise FileNotFoundError(
            f"MBPP data not found at {path}\n"
            "See README.md for download instructions."
        )

    records      = []
    n_total      = 0
    skip_reasons = {}   # reason → count, for the summary

    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue

            n_total += 1
            row = json.loads(line)

            if len(records) >= limit:
                break

            rec = _parse_mbpp_row(row, i, verbose=verbose)
            if rec:
                records.append(rec)
            else:
                # Re-run in verbose=True just to capture the reason for the summary
                # (only when not already verbose, to avoid double-printing)
                if not verbose:
                    _categorise_skip(row, i, skip_reasons)

    # Always print a compact skip summary so the user knows what happened
    n_skipped = n_total - len(records)
    if n_skipped > 0 and not verbose:
        print(f"[data_loader] Skipped {n_skipped} MBPP rows (use --diagnose-mbpp to see details):")
        for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
            print(f"              {count:>4}x  {reason}")

    print(f"[data_loader] Loaded {len(records)} MBPP problems  (file has {n_total} rows)")
    return records


def _categorise_skip(row: dict, index: int, reasons: dict):
    """Silently categorise why a row was skipped, for the summary."""
    code      = row.get("code", "").strip()
    test_list = row.get("test_list", [])
    text      = row.get("text", "").strip()

    if not code:
        key = "empty 'code' field"
    elif not re.search(r"def\s+\w+\s*\(", code):
        key = "no 'def' in code (class-only or expression)"
    elif not text:
        key = "empty 'text' description"
    elif not [t for t in test_list if t.strip()]:
        key = "empty 'test_list' (no assertions)"
    else:
        fn_match = re.search(r"def\s+(\w+)\s*\(", code)
        fn = fn_match.group(1) if fn_match else "?"
        if fn in _SKIP_FUNCTION_NAMES or fn.startswith("__"):
            key = f"dunder/reserved function name '{fn}'"
        else:
            key = "other/exception"

    reasons[key] = reasons.get(key, 0) + 1


# Diagnostic command
def diagnose_mbpp():
    """
    Print a full breakdown of every row in mbpp.jsonl and why it is
    accepted or skipped. Called by: python run.py --diagnose-mbpp
    """
    path = Path(MBPP_JSONL)
    if not path.exists():
        print(f"ERROR: {path} not found")
        return

    print(f"Diagnosing {path} ...\n")
    n_total = n_valid = 0
    reasons = {}

    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            n_total += 1
            row    = json.loads(line)
            rec    = _parse_mbpp_row(row, i, verbose=False)
            if rec:
                n_valid += 1
            else:
                _categorise_skip(row, i, reasons)

    print(f"Total rows    : {n_total}")
    print(f"Valid problems: {n_valid}")
    print(f"Skipped       : {n_total - n_valid}")
    print()
    print("Skip reasons:")
    for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"  {count:>4}x  {reason}")


# New unified-format dataset
def _extract_asserts_from_pytest(test_code: str, fn_name: str) -> List[str]:
    """
    Extract assert statements from a pytest-style test file.

    The new dataset stores tests as a complete pytest file:
      def test_something():
          result = fn(args)
          assert result == expected

    We extract only the assert lines, which is what the prompt builder
    uses to show the model concrete input/output examples.
    Skips pytest.raises blocks (these test error cases, not return values).
    """
    lines = []
    in_raises_block = False
    for line in test_code.splitlines():
        stripped = line.strip()
        # Track pytest.raises context managers — skip asserts inside them
        if 'pytest.raises' in stripped:
            in_raises_block = True
        if in_raises_block:
            # Exit the block when indentation returns to function level
            if stripped and not line.startswith('        ') and 'pytest.raises' not in stripped:
                in_raises_block = False
        if stripped.startswith('assert') and not in_raises_block:
            lines.append(stripped)
    return lines[:8]  # cap at 8 to keep prompt manageable


def _parse_new_dataset_row(row: dict, index: int) -> Optional[ProblemRecord]:
    """
    Parse one row from the new unified-format dataset.

    New schema (all fields are always present for validated entries):
      id            : "HumanEval_NEW_146" or "MBPP_NEW_011"
      source        : "HumanEval" or "MBPP"
      source_id     : "HumanEval/145" or "11"
      description   : natural language problem statement
      entry_point   : function name (e.g. "order_by_points")
      solution_code : complete function implementation
      test_code     : pytest file with test functions
      tests_passed  : integer, number of tests that pass
      validation    : "passed" if the solution passes all tests
    """
    record_id = row.get("id", f"NEW/{index}")

    try:
        # Guard: only process validated entries
        if row.get("validation") != "passed":
            return None

        source      = row.get("source", "Unknown")
        source_id   = row.get("source_id", str(index))
        description = row.get("description", "").strip()
        fn_name     = row.get("entry_point", "").strip()
        solution    = row.get("solution_code", "").strip()
        test_code   = row.get("test_code", "").strip()

        # Guards
        if not fn_name:
            return None
        if not solution:
            return None
        if not description:
            return None
        if fn_name in _SKIP_FUNCTION_NAMES or fn_name.startswith("__"):
            return None

        # Extract signature from solution_code─
        sig_match = re.search(r"(def\s+\w+\s*\(.*?\)\s*(?:->\s*[\w\[\], ]+)?\s*):", solution)
        # sig_match.group(0) already includes the colon from the regex
        signature = sig_match.group(0).strip() if sig_match else f"def {fn_name}(...):"

        # Extract assert lines for prompt examples
        assert_lines = _extract_asserts_from_pytest(test_code, fn_name)

        # Use source_id as the problem_id for traceability
        # Normalise to "HumanEval/145" or "MBPP/11" format
        if "/" in source_id:
            problem_id = source_id           # already in correct format
        else:
            problem_id = f"{source}/{source_id}"

        return ProblemRecord(
            problem_id=problem_id,
            source=source,
            function_name=fn_name,
            nl_description=description,
            function_signature=signature,
            docstring_examples=assert_lines,
            reference_solution=solution,
            existing_tests=assert_lines,
            raw=row,
        )

    except Exception as e:
        print(f"  [data_loader] Failed to parse new dataset row {record_id}: {e}")
        return None


def load_new_dataset(limit: int = NEW_DATASET_LIMIT) -> List[ProblemRecord]:
    """
    Load problems from the new unified-format dataset.
    Skips rows where validation != "passed".
    """
    if limit == 0:
        print("[data_loader] NEW_DATASET_LIMIT=0, skipping new dataset")
        return []

    path = Path(NEW_DATASET_JSONL)
    if not path.exists():
        raise FileNotFoundError(
            f"New dataset not found at {path}\n"
            f"Put your new_dataset.jsonl file at: {path}"
        )

    records = []
    n_total = n_skipped = 0

    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            n_total += 1
            if len(records) >= limit:
                break
            rec = _parse_new_dataset_row(json.loads(line), i)
            if rec:
                records.append(rec)
            else:
                n_skipped += 1

    print(f"[data_loader] Loaded {len(records)} new dataset problems  "
          f"({n_skipped} skipped, {n_total} total rows)")
    return records


# Combined loader
def load_all(
    humaneval_limit: int = HUMANEVAL_LIMIT,
    mbpp_limit: int = MBPP_LIMIT,
    new_dataset_limit: int = NEW_DATASET_LIMIT,
) -> List[ProblemRecord]:
    """Load all configured datasets and return as a combined list."""
    problems = []
    if humaneval_limit > 0:
        problems.extend(load_humaneval(humaneval_limit))
    if mbpp_limit > 0:
        problems.extend(load_mbpp(mbpp_limit))
    if new_dataset_limit > 0 and Path(NEW_DATASET_JSONL).exists():
        problems.extend(load_new_dataset(new_dataset_limit))
    print(f"[data_loader] Total problems loaded: {len(problems)}")
    return problems