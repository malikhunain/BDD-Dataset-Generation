from pathlib import Path

from revalidation.discovery import discover_problems
from revalidation.promotion import move_to_validated


def _make_valid_problem(tmp_path: Path, name: str) -> Path:
    problem_dir = tmp_path / name
    features_dir = problem_dir / "features"
    steps_dir = features_dir / "steps"

    steps_dir.mkdir(parents=True)

    solution_path = problem_dir / "solution.py"
    feature_path = features_dir / "example.feature"
    steps_path = steps_dir / "example_steps.py"

    solution_path.write_text("def example():\n    return 1\n", encoding="utf-8")
    feature_path.write_text("Feature: Example feature\n", encoding="utf-8")
    steps_path.write_text("from behave import given\n", encoding="utf-8")

    return problem_dir


def test_discover_problems_finds_valid_problem(tmp_path):
    _make_valid_problem(tmp_path, "HumanEval_0")

    # This directory should be ignored because it is not a valid problem.
    (tmp_path / "not_a_problem").mkdir()

    problems = discover_problems(tmp_path)

    assert len(problems) == 1

    problem = problems[0]

    assert problem.raw_id == "HumanEval_0"
    assert problem.problem_id == "HumanEval/0"
    assert problem.source == "HumanEval"
    assert problem.problem_dir == tmp_path / "HumanEval_0"
    assert problem.feature_path.name == "example.feature"
    assert problem.steps_path.name == "example_steps.py"
    assert problem.solution_path.name == "solution.py"


def test_discover_problems_requires_solution(tmp_path):
    problem_dir = _make_valid_problem(tmp_path, "MBPP_100")
    (problem_dir / "solution.py").unlink()

    problems = discover_problems(tmp_path)

    assert len(problems) == 0


def test_discover_problems_requires_feature_and_steps(tmp_path):
    problem_dir = _make_valid_problem(tmp_path, "MBPP_200")

    feature_path = problem_dir / "features" / "example.feature"
    feature_path.unlink()

    problems = discover_problems(tmp_path)

    assert len(problems) == 0


def test_move_to_validated_moves_problem(tmp_path):
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()

    validated_dir = tmp_path / "validated_dataset"

    problem_dir = _make_valid_problem(generated_dir, "HumanEval_5")

    assert move_to_validated(problem_dir, destination_root=validated_dir)

    assert not problem_dir.exists()
    assert (validated_dir / "HumanEval_5").exists()
    assert (validated_dir / "HumanEval_5" / "solution.py").exists()


def test_move_to_validated_replaces_existing_problem(tmp_path):
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()

    validated_dir = tmp_path / "validated_dataset"

    problem_dir = _make_valid_problem(generated_dir, "HumanEval_7")

    existing_destination = validated_dir / "HumanEval_7"
    existing_destination.mkdir(parents=True)
    (existing_destination / "old.txt").write_text("old", encoding="utf-8")

    assert move_to_validated(problem_dir, destination_root=validated_dir)

    assert not problem_dir.exists()
    assert (validated_dir / "HumanEval_7").exists()
    assert (validated_dir / "HumanEval_7" / "solution.py").exists()
    assert not (validated_dir / "HumanEval_7" / "old.txt").exists()
