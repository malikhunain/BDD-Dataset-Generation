"""
Compatibility wrapper for prompt building.
"""

from prompts.builder import build_prompt
from prompts.assets import (
    _SYSTEM_PROMPT,
    _FEWSHOT_HE55_FEATURE,
    _FEWSHOT_HE55_STEPS,
    _FEWSHOT_HE7_FEATURE,
    _FEWSHOT_HE7_STEPS,
)

__all__ = [
    "build_prompt",
    "_SYSTEM_PROMPT",
    "_FEWSHOT_HE55_FEATURE",
    "_FEWSHOT_HE55_STEPS",
    "_FEWSHOT_HE7_FEATURE",
    "_FEWSHOT_HE7_STEPS",
]