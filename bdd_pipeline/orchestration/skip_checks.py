"""
Skip checks for the generation pipeline.

Skip priority:
    1. Problem already exists in validated_dataset/
    2. Problem already exists in generated/ and --resume is enabled
"""

from bdd_pipeline.orchestration.artifacts import (
    generated_problem_dir,
    has_feature_and_steps,
    validated_problem_dir,
)


def in_validated_dataset(problem) -> bool:
    """
    Check whether this problem already exists in validated_dataset/.

    This check runs on every pipeline call, regardless of --resume.
    """
    problem_dir = validated_problem_dir(problem)
    return problem_dir.exists() and has_feature_and_steps(problem_dir)


def already_generated(problem) -> bool:
    """
    Check whether this problem already exists in generated/.

    This check is only consulted when --resume is passed.
    """
    problem_dir = generated_problem_dir(problem)
    return problem_dir.exists() and has_feature_and_steps(problem_dir)