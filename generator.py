"""
Compatibility wrapper for the generation pipeline.
"""

from orchestration import (
    run_pipeline,
    run_single,
)
from orchestration.artifacts import (
    has_feature_and_steps as _has_feature_and_steps,
    safe_problem_id as _safe_id,
    safe_problem_id as safe_id,
)
from orchestration.raw_logs import (
    log_raw_response as _log_raw,
)
from orchestration.skip_checks import (
    already_generated as _already_generated,
    in_validated_dataset as _in_validated_dataset,
)

__all__ = [
    "run_pipeline",
    "run_single",
    "safe_id",
    "_safe_id",
    "_log_raw",
    "_has_feature_and_steps",
    "_in_validated_dataset",
    "_already_generated",
]