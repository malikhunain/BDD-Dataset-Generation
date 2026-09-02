from pathlib import Path
from typing import List, Optional

from config import NEW_DATASET_JSONL, NEW_DATASET_LIMIT
from bdd_pipeline.records import ProblemRecord
from bdd_pipeline.utils.jsonl import read_jsonl
from bdd_pipeline.utils.source_parsing import extract_unified_signature
from bdd_pipeline.loaders.mbpp_loader import _is_reserved_function_name


MAX_PROMPT_EXAMPLES = 8


def _extract_asserts_from_pytest(test_code: str) -> List[str]:
    lines: List[str] = []
    in_raises_block = False

    for line in test_code.splitlines():
        stripped = line.strip()

        if "pytest.raises" in stripped:
            in_raises_block = True

        if in_raises_block:
            if (
                stripped
                and not line.startswith("        ")
                and "pytest.raises" not in stripped
            ):
                in_raises_block = False

        if stripped.startswith("assert") and not in_raises_block:
            lines.append(stripped)

    return lines[:MAX_PROMPT_EXAMPLES]


def parse_new_dataset_row(row: dict, index: int) -> Optional[ProblemRecord]:
    record_id = row.get("id", f"NEW/{index}")

    try:
        if row.get("validation") != "passed":
            return None

        source = row.get("source", "Unknown")
        source_id = row.get("source_id", str(index))
        description = row.get("description", "").strip()
        function_name = row.get("entry_point", "").strip()
        solution = row.get("solution_code", "").strip()
        test_code = row.get("test_code", "").strip()

        if not function_name:
            return None

        if not solution:
            return None

        if not description:
            return None

        if _is_reserved_function_name(function_name):
            return None

        if "/" in source_id:
            problem_id = source_id
        else:
            problem_id = f"{source}/{source_id}"

        assert_lines = _extract_asserts_from_pytest(test_code)

        return ProblemRecord(
            problem_id=problem_id,
            source=source,
            function_name=function_name,
            nl_description=description,
            function_signature=extract_unified_signature(solution, function_name),
            docstring_examples=assert_lines,
            reference_solution=solution,
            existing_tests=assert_lines,
            raw=row,
        )

    except Exception as exc:
        print(
            f"  [data_loader] Failed to parse new dataset row "
            f"{record_id}: {exc}"
        )
        return None


def load_new_dataset(limit: int = NEW_DATASET_LIMIT) -> List[ProblemRecord]:
    if limit == 0:
        print("[data_loader] NEW_DATASET_LIMIT=0, skipping new dataset")
        return []

    path = Path(NEW_DATASET_JSONL)

    if not path.exists():
        raise FileNotFoundError(
            f"New dataset not found at {path}\n"
            f"Put your new_dataset.jsonl file at: {path}"
        )

    records: List[ProblemRecord] = []
    total_rows = 0
    skipped_rows = 0

    for index, row in enumerate(read_jsonl(path)):
        total_rows += 1

        if len(records) >= limit:
            break

        record = parse_new_dataset_row(row, index)

        if record:
            records.append(record)
        else:
            skipped_rows += 1

    print(
        f"[data_loader] Loaded {len(records)} new dataset problems  "
        f"({skipped_rows} skipped, {total_rows} total rows)"
    )

    return records