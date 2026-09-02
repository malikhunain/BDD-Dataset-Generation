from pathlib import Path
from typing import List

from config import (
    HUMANEVAL_LIMIT,
    MBPP_LIMIT,
    NEW_DATASET_JSONL,
    NEW_DATASET_LIMIT,
)
from bdd_pipeline.records import ProblemRecord
from bdd_pipeline.loaders.humaneval_loader import load_humaneval
from bdd_pipeline.loaders.mbpp_loader import load_mbpp
from bdd_pipeline.loaders.unified_loader import load_new_dataset


def load_all(
    humaneval_limit: int = HUMANEVAL_LIMIT,
    mbpp_limit: int = MBPP_LIMIT,
    new_dataset_limit: int = NEW_DATASET_LIMIT,
) -> List[ProblemRecord]:
    problems: List[ProblemRecord] = []

    if humaneval_limit > 0:
        problems.extend(load_humaneval(humaneval_limit))

    if mbpp_limit > 0:
        problems.extend(load_mbpp(mbpp_limit))

    if new_dataset_limit > 0 and Path(NEW_DATASET_JSONL).exists():
        problems.extend(load_new_dataset(new_dataset_limit))

    print(f"[data_loader] Total problems loaded: {len(problems)}")
    return problems