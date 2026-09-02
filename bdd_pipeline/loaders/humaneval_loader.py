import re
from pathlib import Path
from typing import List, Optional

from config import HUMANEVAL_JSONL, HUMANEVAL_LIMIT
from bdd_pipeline.records import ProblemRecord
from bdd_pipeline.utils.jsonl import read_jsonl
from bdd_pipeline.utils.source_parsing import extract_legacy_signature


DOCSTRING_RE = re.compile(r'"""(.*?)"""', re.DOTALL)
MAX_PROMPT_EXAMPLES = 8


def _extract_assert_lines(test_code: str, function_name: str) -> List[str]:
    lines = []

    for line in test_code.splitlines():
        stripped = line.strip()
        if stripped.startswith("assert"):
            lines.append(stripped.replace("candidate(", f"{function_name}("))

    return lines[:MAX_PROMPT_EXAMPLES]


def _extract_docstring(prompt: str) -> str:
    match = DOCSTRING_RE.search(prompt)
    return match.group(1).strip() if match else ""


def _extract_docstring_examples(docstring: str) -> List[str]:
    return [
        line.strip()
        for line in docstring.splitlines()
        if ">>>" in line or line.strip().startswith("#")
    ]


def _extract_natural_language_description(docstring: str) -> str:
    description_lines = []

    for line in docstring.splitlines():
        if ">>>" in line:
            break

        if line.strip():
            description_lines.append(line.strip())

    return " ".join(description_lines) if description_lines else docstring[:200]


def parse_humaneval_row(row: dict) -> Optional[ProblemRecord]:
    try:
        task_id = row["task_id"]
        prompt = row["prompt"]
        solution = row["canonical_solution"]
        entry_point = row["entry_point"]
        test_code = row.get("test", "")

        docstring = _extract_docstring(prompt)

        return ProblemRecord(
            problem_id=task_id,
            source="HumanEval",
            function_name=entry_point,
            nl_description=_extract_natural_language_description(docstring),
            function_signature=extract_legacy_signature(prompt, entry_point),
            docstring_examples=_extract_docstring_examples(docstring),
            reference_solution=prompt + solution,
            existing_tests=_extract_assert_lines(test_code, entry_point),
            raw=row,
        )

    except Exception as exc:
        print(
            f"  [data_loader] Failed to parse HumanEval row "
            f"{row.get('task_id')}: {exc}"
        )
        return None


def load_humaneval(limit: int = HUMANEVAL_LIMIT) -> List[ProblemRecord]:
    path = Path(HUMANEVAL_JSONL)

    if not path.exists():
        raise FileNotFoundError(
            f"HumanEval data not found at {path}\n"
            "See README.md for download instructions."
        )

    records: List[ProblemRecord] = []

    for row in read_jsonl(path):
        if len(records) >= limit:
            break

        record = parse_humaneval_row(row)
        if record:
            records.append(record)

    print(f"[data_loader] Loaded {len(records)} HumanEval problems")
    return records