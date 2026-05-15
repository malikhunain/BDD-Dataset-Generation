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

from config import HUMANEVAL_JSONL, MBPP_JSONL, HUMANEVAL_LIMIT, MBPP_LIMIT


@dataclass
class ProblemRecord:
    """Normalised representation of a single coding problem."""
    problem_id:        str            # e.g. "HumanEval/0" or "MBPP/11"
    source:            str            # "HumanEval" or "MBPP"
    function_name:     str            # e.g. "has_close_elements"
    nl_description:    str            # natural-language problem statement
    function_signature: str           # e.g. "def has_close_elements(numbers, threshold):"
    docstring_examples: List[str]     # example lines extracted from docstring
    reference_solution: str           # full reference implementation (ground truth)
    raw:               dict = field(default_factory=dict, repr=False)


# ── HumanEval ───────────────────────────────────────────────────────────────

def _parse_humaneval_row(row: dict) -> Optional[ProblemRecord]:
    """
    HumanEval JSONL fields:
      task_id, prompt, canonical_solution, test, entry_point
    The `prompt` field contains the function signature + docstring.
    """
    try:
        task_id   = row["task_id"]           # "HumanEval/0"
        prompt    = row["prompt"]
        solution  = row["canonical_solution"]
        entry     = row["entry_point"]       # function name

        # Extract docstring from prompt
        doc_match = re.search(r'"""(.*?)"""', prompt, re.DOTALL)
        docstring = doc_match.group(1).strip() if doc_match else ""

        # Extract example lines (lines containing >>>) 
        examples = [
            line.strip()
            for line in docstring.splitlines()
            if ">>>" in line or line.strip().startswith("#")
        ]

        # nl_description: everything in docstring before the first >>>
        desc_lines = []
        for line in docstring.splitlines():
            if ">>>" in line:
                break
            if line.strip():
                desc_lines.append(line.strip())
        nl_description = " ".join(desc_lines) if desc_lines else docstring[:200]

        # Signature: first def line in prompt
        sig_match = re.search(r"(def\s+\w+\s*\(.*?\)\s*(?:->\s*\S+)?\s*):", prompt)
        signature = (sig_match.group(0) + ":").strip() if sig_match else f"def {entry}(...):"

        # Full reference = prompt + canonical_solution (makes a runnable module)
        reference = prompt + solution

        return ProblemRecord(
            problem_id=task_id,
            source="HumanEval",
            function_name=entry,
            nl_description=nl_description,
            function_signature=signature,
            docstring_examples=examples,
            reference_solution=reference,
            raw=row,
        )
    except Exception as e:
        print(f"  [data_loader] Failed to parse HumanEval row {row.get('task_id')}: {e}")
        return None


def load_humaneval(limit: int = HUMANEVAL_LIMIT) -> List[ProblemRecord]:
    path = Path(HUMANEVAL_JSONL)
    if not path.exists():
        raise FileNotFoundError(
            f"HumanEval data not found at {path}\n"
            "See README.md for download instructions."
        )
    records = []
    with open(path) as f:
        for line in f:
            if len(records) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rec = _parse_humaneval_row(row)
            if rec:
                records.append(rec)
    print(f"[data_loader] Loaded {len(records)} HumanEval problems")
    return records


# ── MBPP ────────────────────────────────────────────────────────────────────

# Skip MBPP entries where the extracted function name is not useful
SKIP_FUNCTION_NAMES = {"__init__", "__str__", "__repr__", "__eq__", "main"}

def _parse_mbpp_row(row: dict, index: int) -> Optional[ProblemRecord]:
    """
    MBPP JSONL fields:
      task_id, text, code, test_list, test_setup_code, challenge_test_list
    """
    try:
        task_id   = f"MBPP/{row.get('task_id', index)}"
        text      = row["text"]          # natural language description
        code      = row["code"]          # reference solution
        tests     = row.get("test_list", [])

        # Extract function name from the first `def` in reference code
        fn_match  = re.search(r"def\s+(\w+)\s*\(", code)
        fn_name   = fn_match.group(1) if fn_match else f"mbpp_fn_{index}"

        # Filter out class constructors and other non-algorithmic functions
        if fn_name in SKIP_FUNCTION_NAMES or fn_name.startswith("__"):
            print(f"  [data_loader] Skipping MBPP/{row.get('task_id', index)}: "
                f"function name '{fn_name}' is not a valid algorithmic problem")
            return None

        # Extract signature
        sig_match = re.search(r"(def\s+\w+\s*\(.*?\)\s*(?:->\s*\S+)?\s*):", code)
        signature = (sig_match.group(0) + ":").strip() if sig_match else f"def {fn_name}(...):"

        # Use the test_list entries as docstring examples
        examples = [t.strip() for t in tests if t.strip()]

        return ProblemRecord(
            problem_id=task_id,
            source="MBPP",
            function_name=fn_name,
            nl_description=text.strip(),
            function_signature=signature,
            docstring_examples=examples,
            reference_solution=code,
            raw=row,
        )
    except Exception as e:
        print(f"  [data_loader] Failed to parse MBPP row index {index}: {e}")
        return None


def load_mbpp(limit: int = MBPP_LIMIT) -> List[ProblemRecord]:
    path = Path(MBPP_JSONL)
    if not path.exists():
        raise FileNotFoundError(
            f"MBPP data not found at {path}\n"
            "See README.md for download instructions."
        )
    records = []
    with open(path) as f:
        for i, line in enumerate(f):
            if len(records) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rec = _parse_mbpp_row(row, i)
            if rec:
                records.append(rec)
    print(f"[data_loader] Loaded {len(records)} MBPP problems")
    return records


def load_all(
    humaneval_limit: int = HUMANEVAL_LIMIT,
    mbpp_limit: int = MBPP_LIMIT,
) -> List[ProblemRecord]:
    """Load both datasets and return as a combined list."""
    problems = []
    problems.extend(load_humaneval(humaneval_limit))
    problems.extend(load_mbpp(mbpp_limit))
    print(f"[data_loader] Total problems loaded: {len(problems)}")
    return problems