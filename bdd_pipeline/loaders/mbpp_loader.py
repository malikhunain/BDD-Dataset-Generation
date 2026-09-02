from pathlib import Path
from typing import Dict, List, Optional

from config import MBPP_JSONL, MBPP_LIMIT
from bdd_pipeline.records import ProblemRecord
from bdd_pipeline.utils.jsonl import read_jsonl
from bdd_pipeline.utils.source_parsing import (
    FUNCTION_NAME_RE,
    extract_function_name,
    extract_legacy_signature,
)

MAX_PROMPT_EXAMPLES = 8
SKIP_FUNCTION_NAMES = frozenset(
    {
        " init ",
        " str ",
        " repr ",
        " eq ",
        " hash ",
        " len ",
        " iter ",
        " next ",
        "main ",
    }
)


def _is_reserved_function_name(function_name: str) -> bool:
    return (
        function_name in SKIP_FUNCTION_NAMES
        or function_name.startswith("__")
    )


def parse_mbpp_row(
    row: dict,
    index: int,
    verbose: bool = False,
) -> Optional[ProblemRecord]:
    task_id = f"MBPP/{row.get('task_id', index)}"

    try:
        text = row.get("text", "").strip()
        code = row.get("code", "").strip()
        test_list = row.get("test_list", [])

        if not code:
            if verbose:
                print(f"  [data_loader] Skipping {task_id}: empty 'code' field")
            return None

        function_name = extract_function_name(code)
        if not function_name:
            if verbose:
                print(f"  [data_loader] Skipping {task_id}: no 'def' found in code")
            return None

        if _is_reserved_function_name(function_name):
            print(
                f"  [data_loader] Skipping {task_id}: "
                f"'{function_name}' is not a valid algorithmic function"
            )
            return None

        if not text:
            if verbose:
                print(f"  [data_loader] Skipping {task_id}: empty 'text' field")
            return None

        clean_tests = [test.strip() for test in test_list if test.strip()]
        if not clean_tests:
            if verbose:
                print(
                    f"  [data_loader] Skipping {task_id}: "
                    "no test assertions in 'test_list'"
                )
            return None

        return ProblemRecord(
            problem_id=task_id,
            source="MBPP",
            function_name=function_name,
            nl_description=text,
            function_signature=extract_legacy_signature(code, function_name),
            docstring_examples=clean_tests,
            reference_solution=code,
            existing_tests=clean_tests,
            raw=row,
        )

    except Exception as exc:
        print(f"  [data_loader] Failed to parse {task_id}: {exc}")
        return None


def categorize_mbpp_skip(row: dict, index: int, reasons: Dict[str, int]) -> None:
    code = row.get("code", "").strip()
    test_list = row.get("test_list", [])
    text = row.get("text", "").strip()

    if not code:
        reason = "empty 'code' field"

    elif not FUNCTION_NAME_RE.search(code):
        reason = "no 'def' in code (class-only or expression)"

    elif not text:
        reason = "empty 'text' description"

    elif not [test for test in test_list if test.strip()]:
        reason = "empty 'test_list' (no assertions)"

    else:
        function_name = extract_function_name(code) or "?"

        if _is_reserved_function_name(function_name):
            reason = f"dunder/reserved function name '{function_name}'"
        else:
            reason = "other/exception"

    reasons[reason] = reasons.get(reason, 0) + 1


def load_mbpp(
    limit: int = MBPP_LIMIT,
    verbose: bool = False,
) -> List[ProblemRecord]:
    path = Path(MBPP_JSONL)

    if not path.exists():
        raise FileNotFoundError(
            f"MBPP data not found at {path}\n"
            "See README.md for download instructions."
        )

    records: List[ProblemRecord] = []
    skip_reasons: Dict[str, int] = {}
    total_rows = 0

    for index, row in enumerate(read_jsonl(path)):
        total_rows += 1

        if len(records) >= limit:
            break

        record = parse_mbpp_row(row, index, verbose=verbose)

        if record:
            records.append(record)
        elif not verbose:
            categorize_mbpp_skip(row, index, skip_reasons)

    skipped_rows = total_rows - len(records)

    if skipped_rows > 0 and not verbose:
        print(
            f"[data_loader] Skipped {skipped_rows} MBPP rows "
            "(use --diagnose-mbpp to see details):"
        )

        for reason, count in sorted(skip_reasons.items(), key=lambda item: -item[1]):
            print(f"              {count:>4}x  {reason}")

    print(
        f"[data_loader] Loaded {len(records)} MBPP problems  "
        f"(file has {total_rows} rows)"
    )

    return records


def diagnose_mbpp() -> None:
    path = Path(MBPP_JSONL)

    if not path.exists():
        print(f"ERROR: {path} not found")
        return

    print(f"Diagnosing {path} ...\n")

    total_rows = 0
    valid_rows = 0
    reasons: Dict[str, int] = {}

    for index, row in enumerate(read_jsonl(path)):
        total_rows += 1

        record = parse_mbpp_row(row, index, verbose=False)

        if record:
            valid_rows += 1
        else:
            categorize_mbpp_skip(row, index, reasons)

    print(f"Total rows    : {total_rows}")
    print(f"Valid problems: {valid_rows}")
    print(f"Skipped       : {total_rows - valid_rows}")
    print()
    print("Skip reasons:")

    for reason, count in sorted(reasons.items(), key=lambda item: -item[1]):
        print(f"  {count:>4}x  {reason}")