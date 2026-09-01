"""
Discovery of already-generated problems.

A valid generated problem directory must contain:

    solution.py
    features/*.feature
    features/steps/*_steps.py
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class DiscoveredProblem:
    """
    A generated problem that can be re-validated.
    """

    problem_id: str
    raw_id: str
    source: str
    problem_dir: Path
    feature_path: Path
    steps_path: Path
    solution_path: Path


def discover_problems(generated_dir: Path) -> List[DiscoveredProblem]:
    """
    Walk generated/ and find every valid problem directory.
    """
    problems: List[DiscoveredProblem] = []

    for problem_dir in sorted(generated_dir.iterdir()):
        if not problem_dir.is_dir():
            continue

        solution_path = problem_dir / "solution.py"
        features_dir = problem_dir / "features"
        steps_dir = features_dir / "steps"

        if not solution_path.exists():
            continue

        feature_files = (
            list(features_dir.glob("*.feature"))
            if features_dir.exists()
            else []
        )

        steps_files = (
            list(steps_dir.glob("*_steps.py"))
            if steps_dir.exists()
            else []
        )

        if not feature_files or not steps_files:
            continue

        raw_id = problem_dir.name

        # Example:
        #   HumanEval_0 -> HumanEval/0
        #   MBPP_602    -> MBPP/602
        problem_id = raw_id.replace("_", "/", 1)
        source = problem_id.split("/")[0]

        problems.append(
            DiscoveredProblem(
                problem_id=problem_id,
                raw_id=raw_id,
                source=source,
                problem_dir=problem_dir,
                feature_path=feature_files[0],
                steps_path=steps_files[0],
                solution_path=solution_path,
            )
        )

    return problems