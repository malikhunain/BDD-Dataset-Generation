"""
Artifact path helpers for the generation pipeline.
"""

from pathlib import Path
from config import GENERATED_DIR, VALIDATED_DATASET_DIR

try:
    from output_parser import _problem_dir as _legacy_generated_problem_dir
except ImportError:
    try:
        from output_parser import problem_dir as _legacy_generated_problem_dir
    except ImportError:
        _legacy_generated_problem_dir = None


def safe_problem_id(problem) -> str:
    """
    Convert a problem ID into a filesystem-safe directory name.

    Example:
        HumanEval/0 -> HumanEval_0
        MBPP/602    -> MBPP_602
    """
    return problem.problem_id.replace("/", "_")


def validated_problem_dir(problem) -> Path:
    """Return the validated_dataset directory for a problem."""
    return VALIDATED_DATASET_DIR / safe_problem_id(problem)


def generated_problem_dir(problem) -> Path:
    """
    Return the generated directory for a problem.
    """
    if _legacy_generated_problem_dir is not None:
        return _legacy_generated_problem_dir(problem)

    return GENERATED_DIR / safe_problem_id(problem)


def has_feature_and_steps(directory: Path) -> bool:
    """
    Return True if the problem directory contains both:
      - at least one .feature file
      - at least one _steps.py file
    """
    features_dir = directory / "features"
    steps_dir = features_dir / "steps"

    if not features_dir.exists():
        return False

    has_feature = any(features_dir.glob("*.feature"))
    has_steps = steps_dir.exists() and any(steps_dir.glob("*_steps.py"))

    return has_feature and has_steps