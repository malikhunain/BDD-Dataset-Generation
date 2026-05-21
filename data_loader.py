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

# Functions with these names are not valid standalone algorithmic problems
_SKIP_FUNCTION_NAMES = frozenset({
    "__init__", "__str__", "__repr__", "__eq__", "__hash__",
    "__len__", "__iter__", "__next__", "main",
})


@dataclass
class ProblemRecord:
    """Normalised representation of a single coding problem."""
    problem_id:          str           # e.g. "HumanEval/0" or "MBPP/11"
    source:              str           # "HumanEval" or "MBPP"
    function_name:       str           # e.g. "has_close_elements"
    nl_description:      str           # natural-language problem statement
    function_signature:  str           # e.g. "def has_close_elements(numbers, threshold):"
    docstring_examples:  List[str]     # >>> example lines from docstring
    reference_solution:  str           # complete runnable reference implementation
    existing_tests:      List[str]     # original test assertions from the dataset
    raw:                 dict = field(default_factory=dict, repr=False)


# ── HumanEval ────────────────────────────────────────────────────────────────

def _parse_humaneval_row(row: dict) -> Optional[ProblemRecord]:
    """
    HumanEval JSONL fields:
      task_id, prompt, canonical_solution, test, entry_point

    The `test` field contains a check() function with assert statements, e.g.:
      def check(candidate):
          assert candidate([1.0, 2.0, 3.9], 0.3) == True
          assert candidate([1.0, 2.0, 3.9], 0.05) == False
    """
    try:
        task_id  = row["task_id"]
        prompt   = row["prompt"]
        solution = row["canonical_solution"]
        entry    = row["entry_point"]
        test_raw = row.get("test", "")

        # Extract docstring
        doc_match = re.search(r'"""(.*?)"""', prompt, re.DOTALL)
        docstring = doc_match.group(1).strip() if doc_match else ""

        # >>> example lines
        examples = [
            line.strip()
            for line in docstring.splitlines()
            if ">>>" in line or line.strip().startswith("#")
        ]

        # nl_description: docstring text before the first >>>
        desc_lines = []
        for line in docstring.splitlines():
            if ">>>" in line:
                break
            if line.strip():
                desc_lines.append(line.strip())
        nl_description = " ".join(desc_lines) if desc_lines else docstring[:200]

        # Signature
        sig_match = re.search(r"(def\s+\w+\s*\(.*?\)\s*(?:->\s*\S+)?\s*):", prompt)
        signature = (sig_match.group(0) + ":").strip() if sig_match else f"def {entry}(...):"

        # Full reference = prompt + canonical_solution (runnable module)
        reference = prompt + solution

        # Extract individual assert lines from the test function
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


def _extract_assert_lines(test_code: str, fn_name: str) -> List[str]:
    """
    Extract individual assert statements from HumanEval's check() function.
    Replaces 'candidate(' with '<fn_name>(' so the LLM sees the real name.

    Input:
      def check(candidate):
          assert candidate([1.0, 2.0], 0.5) == False

    Output:
      ['assert has_close_elements([1.0, 2.0], 0.5) == False']
    """
    lines = []
    for line in test_code.splitlines():
        stripped = line.strip()
        if stripped.startswith("assert"):
            # Replace 'candidate(' with the actual function name
            normalised = stripped.replace("candidate(", f"{fn_name}(")
            lines.append(normalised)
    return lines[:8]  # cap at 8 to keep the prompt from getting too long


# ── MBPP ─────────────────────────────────────────────────────────────────────

def _parse_mbpp_row(row: dict, index: int) -> Optional[ProblemRecord]:
    """
    MBPP JSONL fields:
      task_id, text, code, test_list, test_setup_code, challenge_test_list

    test_list contains ready-made assert statements, e.g.:
      ["assert remove_dirty_chars('probleesome', 'pro') == 'bleesme'",
       "assert remove_dirty_chars('fight', 'ght') == 'fi'"]
    """
    try:
        task_id    = f"MBPP/{row.get('task_id', index)}"
        text       = row["text"]
        code       = row["code"]
        test_list  = row.get("test_list", [])

        # Extract function name
        fn_match = re.search(r"def\s+(\w+)\s*\(", code)
        fn_name  = fn_match.group(1) if fn_match else f"mbpp_fn_{index}"

        # Skip non-algorithmic entries
        if fn_name in _SKIP_FUNCTION_NAMES or fn_name.startswith("__"):
            print(
                f"  [data_loader] Skipping {task_id}: "
                f"'{fn_name}' is not a valid algorithmic function"
            )
            return None

        # Signature
        sig_match = re.search(r"(def\s+\w+\s*\(.*?\)\s*(?:->\s*\S+)?\s*):", code)
        signature = (sig_match.group(0) + ":").strip() if sig_match else f"def {fn_name}(...):"

        # test_list doubles as both docstring examples and existing tests
        existing_tests = [t.strip() for t in test_list if t.strip()]

        return ProblemRecord(
            problem_id=task_id,
            source="MBPP",
            function_name=fn_name,
            nl_description=text.strip(),
            function_signature=signature,
            docstring_examples=existing_tests,   # used for examples section
            reference_solution=code,
            existing_tests=existing_tests,        # also used for tests section
            raw=row,
        )
    except Exception as e:
        print(f"  [data_loader] Failed to parse MBPP row index {index}: {e}")
        return None


# ── Loaders ───────────────────────────────────────────────────────────────────

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
            rec = _parse_humaneval_row(json.loads(line))
            if rec:
                records.append(rec)
    print(f"[data_loader] Loaded {len(records)} HumanEval problems")
    return records


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
            rec = _parse_mbpp_row(json.loads(line), i)
            if rec:
                records.append(rec)
    print(f"[data_loader] Loaded {len(records)} MBPP problems")
    return records


def load_all(
    humaneval_limit: int = HUMANEVAL_LIMIT,
    mbpp_limit:      int = MBPP_LIMIT,
) -> List[ProblemRecord]:
    problems = []
    problems.extend(load_humaneval(humaneval_limit))
    problems.extend(load_mbpp(mbpp_limit))
    print(f"[data_loader] Total problems loaded: {len(problems)}")
    return problems