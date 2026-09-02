"""
CSV serialization for run records.

The CSV format is intentionally preserved exactly, including column order and numeric formatting.
"""

from bdd_pipeline.reporting.models import RunRecord

CSV_FIELDNAMES = [
    "problem_id",
    "source",
    "function_name",
    "status",
    "scenarios_passed",
    "scenarios_total",
    "steps_passed",
    "steps_total",
    "scenario_pass_rate",
    "step_pass_rate",
    "generation_time_s",
    "retry_count",
    "error_message",
]

def to_csv_row(record: RunRecord) -> dict:
    """
    Convert a RunRecord into one CSV row.

    Formatting rules:
    - pass rates use 3 decimal places
    - generation time uses 1 decimal place
    - error messages are truncated to 200 characters
    """
    return {
        "problem_id": record.problem_id,
        "source": record.source,
        "function_name": record.function_name,
        "status": record.status,
        "scenarios_passed": record.scenarios_passed,
        "scenarios_total": record.scenarios_total,
        "steps_passed": record.steps_passed,
        "steps_total": record.steps_total,
        "scenario_pass_rate": f"{record.scenario_pass_rate:.3f}",
        "step_pass_rate": f"{record.step_pass_rate:.3f}",
        "generation_time_s": f"{record.generation_time_s:.1f}",
        "retry_count": record.retry_count,
        "error_message": record.error_message[:200] if record.error_message else "",
    }