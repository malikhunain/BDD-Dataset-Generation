"""
Raw LLM response logging.
"""

from config import LOGS_DIR, LOG_RAW_RESPONSES
from bdd_pipeline.orchestration.artifacts import safe_problem_id


def log_raw_response(problem, attempt: int, raw: str) -> None:
    """
    Save the raw LLM response for debugging and reproducibility.
    """
    if not LOG_RAW_RESPONSES:
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    path = LOGS_DIR / f"{safe_problem_id(problem)}_attempt{attempt}.txt"
    path.write_text(raw, encoding="utf-8")