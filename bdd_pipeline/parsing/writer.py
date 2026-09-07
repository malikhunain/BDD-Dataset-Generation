import re
from pathlib import Path
from bdd_pipeline.parsing.models import ParsedOutput, ParseError
from bdd_pipeline.parsing.extraction import _extract_blocks
from bdd_pipeline.parsing.validation import _validate_feature, _validate_steps
from bdd_pipeline.parsing.fixers import _fix_steps

def _problem_dir(problem):
    from config import GENERATED_DIR
    safe_id = problem.problem_id.replace("/", "_")
    return GENERATED_DIR / safe_id


def write_solution(problem) -> Path:
    d = _problem_dir(problem)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "solution.py"
    path.write_text(problem.reference_solution, encoding="utf-8")
    return path


def parse_and_write(problem, raw_response: str) -> ParsedOutput:
    """
    Parse the LLM response, auto-fix common mistakes, validate, write to disk.
    Raises ParseError if parsing or validation fails after fixes.
    """
    feature_text, steps_text = _extract_blocks(raw_response)

    if feature_text is None:
        raise ParseError(
            "Could not extract a Gherkin feature block from LLM response. "
            f"Response starts with: {raw_response[:300]!r}"
        )
    if steps_text is None:
        raise ParseError(
            "Could not extract a Python step definitions block from LLM response."
        )

    _validate_feature(feature_text)
    steps_text = _fix_steps(steps_text, expected_function_name=problem.function_name)
    _validate_steps(steps_text, problem.function_name)

    d = _problem_dir(problem)
    steps_d = d / "features" / "steps"
    steps_d.mkdir(parents=True, exist_ok=True)

    feature_path = d / "features" / f"{problem.function_name}.feature"
    steps_path = steps_d / f"{problem.function_name}_steps.py"
    solution_path = write_solution(problem)

    feature_path.write_text(feature_text, encoding="utf-8")
    steps_path.write_text(steps_text,     encoding="utf-8")

    return ParsedOutput(
        feature_content=feature_text,
        steps_content=steps_text,
        feature_path=feature_path,
        steps_path=steps_path,
        solution_path=solution_path,
    )
