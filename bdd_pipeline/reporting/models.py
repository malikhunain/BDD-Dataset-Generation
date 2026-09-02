"""
Data model for one pipeline run record.
"""

from dataclasses import dataclass


@dataclass
class RunRecord:
    """
    One row in the results CSV.

    Combines generation metadata with the final validation outcome.
    """

    problem_id: str
    source: str
    function_name: str
    status: str
    scenarios_passed: int
    scenarios_total: int
    steps_passed: int
    steps_total: int
    scenario_pass_rate: float
    step_pass_rate: float
    generation_time_s: float
    error_message: str
    retry_count: int