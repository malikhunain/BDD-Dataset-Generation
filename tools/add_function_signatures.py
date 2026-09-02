"""
Add function_signature to an existing BDD dataset JSONL file.

This script preserves all existing fields and appends function_signature.

Usage:
    python tools/add_function_signatures.py input_dataset.jsonl output_dataset.jsonl
"""

import argparse
import json
from pathlib import Path

from bdd_pipeline.signatures import (
    extract_function_signature,
    infer_function_name_from_steps,
)


def add_signatures(input_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open(encoding="utf-8") as input_file:
        with output_path.open("w", encoding="utf-8") as output_file:
            for line in input_file:
                line = line.strip()

                if not line:
                    continue

                record = json.loads(line)

                preferred_names = []

                if record.get("function_name"):
                    preferred_names.append(record["function_name"])

                inferred_name = infer_function_name_from_steps(
                    record.get("steps_text", "")
                )

                if inferred_name:
                    preferred_names.append(inferred_name)

                record["function_signature"] = extract_function_signature(
                    record.get("solution_text", ""),
                    preferred_names=preferred_names,
                )

                output_file.write(
                    json.dumps(record, ensure_ascii=False) + "\n"
                )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Add function_signature to an existing BDD dataset JSONL file."
        )
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Existing dataset JSONL file",
    )

    parser.add_argument(
        "output",
        type=Path,
        help="New dataset JSONL file with function_signature added",
    )

    args = parser.parse_args()

    add_signatures(args.input, args.output)
    print(f"Wrote updated dataset to {args.output}")


if __name__ == "__main__":
    main()