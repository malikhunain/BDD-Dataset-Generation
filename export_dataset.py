"""
Export validated_dataset/ to the final BDD dataset JSONL file.

Usage:
    python export_dataset.py
    python export_dataset.py --input-dir validated_dataset
    python export_dataset.py --output enhanced_dataset/bdd_dataset.jsonl
"""

import argparse
from pathlib import Path

from config import VALIDATED_DATASET_DIR

try:
    from config import EXPORT_DATASET_JSONL
except ImportError:
    EXPORT_DATASET_JSONL = (
        VALIDATED_DATASET_DIR.parent
        / "enhanced_dataset"
        / "bdd_dataset.jsonl"
    )

from bdd_pipeline.export import export_dataset


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export validated_dataset/ to a JSONL dataset. "
            "Includes the function_signature field for every problem."
        )
    )

    parser.add_argument(
        "--input-dir",
        type=Path,
        default=VALIDATED_DATASET_DIR,
        help=(
            "Directory containing validated problems "
            f"(default: {VALIDATED_DATASET_DIR})"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=EXPORT_DATASET_JSONL,
        help=(
            "Output JSONL dataset path "
            f"(default: {EXPORT_DATASET_JSONL})"
        ),
    )

    args = parser.parse_args()

    export_dataset(
        input_dir=args.input_dir,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()