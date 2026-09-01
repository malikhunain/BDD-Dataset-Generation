"""
Promotion of passing problems into validated_dataset/.
"""

import shutil
from pathlib import Path
from typing import Optional

from config import VALIDATED_DATASET_DIR


def move_to_validated(
    problem_dir: Path,
    destination_root: Optional[Path] = None,
) -> bool:
    """
    Move a problem directory from generated/ to validated_dataset/.

    If a copy already exists in validated_dataset/, it is replaced.

    Returns True on success, False on error.
    """
    root = (
        Path(destination_root)
        if destination_root is not None
        else VALIDATED_DATASET_DIR
    )

    root.mkdir(parents=True, exist_ok=True)

    destination = root / problem_dir.name

    try:
        if destination.exists():
            shutil.rmtree(destination)

        shutil.move(str(problem_dir), str(destination))
        return True

    except Exception as e:
        print(
            f"         [MOVE ERROR] Could not move "
            f"{problem_dir.name}: {e}"
        )
        return False