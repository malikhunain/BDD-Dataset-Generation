"""
Export validated_dataset/ to a JSONL dataset.

This exporter reads each validated problem directory and writes a final
dataset record containing:

    id
    source
    feature_text
    steps_text
    solution_text
    num_scenarios
    num_steps
    function_signature

The function_signature field is extracted from solution_text using the
expected function name inferred from the feature/steps files.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, Optional
from config import VALIDATED_DATASET_DIR, BEHAVE_TIMEOUT
from bdd_pipeline.signatures import (
    extract_function_signature,
    infer_function_name_from_steps,
)

try:
    from config import EXPORT_DATASET_JSONL
except ImportError:
    EXPORT_DATASET_JSONL = (
        VALIDATED_DATASET_DIR.parent
        / "enhanced_dataset"
        / "bdd_dataset.jsonl"
    )

def count_scenarios_and_steps(feature_path):
    result = subprocess.run(
        [
            "behave",
            "--dry-run",
            feature_path,
        ],
        capture_output=True,
        text=True,
        timeout=BEHAVE_TIMEOUT
    )

    output = result.stdout + result.stderr

    t_scenarios = 0
    t_steps = 0

    for line in output.splitlines():
        stripped = line.strip()

        if not stripped or not stripped[0].isdigit():
            continue

        match = re.search(r"(\d+)\s+untested", stripped)
        if not match:
            continue

        total = int(match.group(1))

        if "scenarios" in stripped:
            t_scenarios = total
        elif "steps" in stripped:
            t_steps = total

    return t_scenarios, t_steps


def _infer_source(problem_id: str) -> str:
    """
    Infer source dataset from a problem directory name.

    Examples:
        HumanEval_0       -> HumanEval
        MBPP_602          -> MBPP
        HumanEval_NEW_146 -> HumanEval
        MBPP_NEW_011      -> MBPP
    """
    if "_" in problem_id:
        return problem_id.split("_", 1)[0]

    return "Unknown"


def build_dataset_record(problem_dir: Path) -> Optional[Dict]:
    """
    Build one JSONL dataset record from a validated problem directory.

    Expected structure:

        HumanEval_0/
            solution.py
            features/
                has_close_elements.feature
                steps/
                    has_close_elements_steps.py
    """
    if not problem_dir.is_dir():
        return None

    solution_path = problem_dir / "solution.py"
    features_dir = problem_dir / "features"
    steps_dir = features_dir / "steps"

    if not solution_path.exists():
        return None

    if not features_dir.exists() or not steps_dir.exists():
        return None

    feature_files = sorted(features_dir.glob("*.feature"))
    steps_files = sorted(steps_dir.glob("*_steps.py"))

    if not feature_files or not steps_files:
        return None

    feature_path = feature_files[0]
    steps_path = steps_files[0]

    feature_text = feature_path.read_text(encoding="utf-8")
    steps_text = steps_path.read_text(encoding="utf-8")
    solution_text = solution_path.read_text(encoding="utf-8")

    t_scenarios, t_steps = count_scenarios_and_steps(feature_path=feature_path)
    function_name_from_feature = feature_path.stem
    function_name_from_steps = infer_function_name_from_steps(steps_text)

    preferred_names = [
        name
        for name in (
            function_name_from_feature,
            function_name_from_steps,
        )
        if name
    ]

    function_signature = extract_function_signature(
        solution_text,
        preferred_names=preferred_names,
    )

    return {
        "id": problem_dir.name,
        "source": _infer_source(problem_dir.name),
        "feature_text": feature_text,
        "steps_text": steps_text,
        "function_signature": function_signature,
        "solution_text": solution_text,
        "num_scenarios": t_scenarios,
        "num_steps": t_steps,
    }


def export_dataset(
    input_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> int:
    """
    Export all valid problems from validated_dataset/ into a JSONL file.

    Returns the number of exported records.
    """
    input_dir = Path(input_dir) if input_dir else Path(VALIDATED_DATASET_DIR)
    output_path = (
        Path(output_path)
        if output_path
        else Path(EXPORT_DATASET_JSONL)
    )

    if not input_dir.exists():
        raise FileNotFoundError(
            f"Validated dataset directory not found at {input_dir}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    exported_count = 0

    with output_path.open("w", encoding="utf-8") as output_file:
        for problem_dir in sorted(input_dir.iterdir()):
            record = build_dataset_record(problem_dir)

            if record is None:
                continue

            output_file.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )

            exported_count += 1

    print(
        f"[export] Wrote {exported_count} records to {output_path}"
    )

    return exported_count