"""
Tier-2 Refinement Runner.

Reads validated problems, asks the LLM to improve behavioral intent, 
and uses the shared validation component to ensure the refined steps still pass.
"""

import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from bdd_pipeline.llm import OllamaClient, OllamaError
from bdd_pipeline.parsing import ParsedOutput
from bdd_pipeline.validation import ValidationResult, validate
from bdd_pipeline.refinement.prompts import REFINE_SYSTEM_PROMPT


@dataclass
class RefinementResult:
    problem_id: str
    status: str  # "PASS", "PASS_RETRY", "FAIL", "LLM_ERROR"
    scenarios_passed: int = 0
    scenarios_total: int = 0
    error: str = ""


def _extract_blocks(raw: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract Gherkin and Python blocks from the LLM refinement response."""
    gherkin_re = re.compile(r"```(?:gherkin|feature)\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
    python_re = re.compile(r"```(?:python|py)\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
    
    g_matches = gherkin_re.findall(raw)
    p_matches = python_re.findall(raw)
    
    if g_matches and p_matches:
        return g_matches[0].strip(), p_matches[0].strip()
    return None, None


def refine_problem(
    problem_dir: Path,
    client: OllamaClient,
    max_retries: int = 1,
) -> RefinementResult:
    """
    Refine a single problem's When steps for behavioral intent.
    """
    problem_id = problem_dir.name
    feature_path = next((problem_dir / "features").glob("*.feature"), None)
    steps_path = next((problem_dir / "features" / "steps").glob("*_steps.py"), None)
    solution_path = problem_dir / "solution.py"

    if not feature_path or not steps_path or not solution_path.exists():
        return RefinementResult(problem_id, "FAIL", error="Missing files")

    original_feature = feature_path.read_text(encoding="utf-8")
    original_steps = steps_path.read_text(encoding="utf-8")
    
    # We use a temporary directory to test the refined code without touching the original
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        tmp_features = tmp_dir / "features"
        tmp_steps_dir = tmp_features / "steps"
        tmp_steps_dir.mkdir(parents=True)
        
        tmp_feature_path = tmp_features / feature_path.name
        tmp_steps_path = tmp_steps_dir / steps_path.name
        
        # Copy solution to tmp so relative paths in load_solution() still work
        tmp_solution_path = tmp_dir / "solution.py"
        shutil.copy2(solution_path, tmp_solution_path)

        behave_error = ""
        
        for attempt in range(max_retries + 1):
            prompt = (
                f"{REFINE_SYSTEM_PROMPT}\n\n"
                f"PROBLEM ID: {problem_id}\n"
                f"{f'BEHAVE ERROR FROM PREVIOUS ATTEMPT:\\n{behave_error}\\n\\nFix the step matching.' if behave_error else ''}"
                f"CURRENT FEATURE FILE:\n```gherkin\n{original_feature}\n```\n\n"
                f"CURRENT STEP DEFINITIONS:\n```python\n{original_steps}\n```\n\n"
                f"Start immediately with ### FEATURE FILE."
            )

            try:
                raw_response, _ = client.generate(prompt)
            except OllamaError as e:
                return RefinementResult(problem_id, "LLM_ERROR", error=str(e))

            new_feature, new_steps = _extract_blocks(raw_response)
            if not new_feature or not new_steps:
                behave_error = "LLM failed to produce parseable feature+steps blocks."
                continue

            # Write to tmp and validate using the SHARED validator
            tmp_feature_path.write_text(new_feature, encoding="utf-8")
            tmp_steps_path.write_text(new_steps, encoding="utf-8")

            parsed = ParsedOutput(
                feature_content=new_feature,
                steps_content=new_steps,
                feature_path=tmp_feature_path,
                steps_path=tmp_steps_path,
                solution_path=tmp_solution_path,
            )

            # Reuse the exact same Behave runner as the main pipeline!
            result: ValidationResult = validate(parsed)

            if result.status == "PASS":
                status = "PASS" if attempt == 0 else "PASS_RETRY"
                return RefinementResult(
                    problem_id, status, 
                    result.scenarios_passed, result.scenarios_total
                )

            # Prepare error for retry
            behave_error = result.error_message or "Scenarios failed"

    return RefinementResult(
        problem_id, "FAIL", 
        result.scenarios_passed if 'result' in locals() else 0,
        result.scenarios_total if 'result' in locals() else 0,
        behave_error[:300]
    )