from dataclasses import dataclass, field
from typing import List


@dataclass
class ProblemRecord:
    """
    Normalized representation of a programming problem used by the generation
    pipeline.

    This object is the boundary between dataset loading and prompt generation.
    Changing any field value may change generated prompts and therefore the
    final dataset.
    """

    problem_id: str
    source: str
    function_name: str
    nl_description: str
    function_signature: str
    docstring_examples: List[str]
    reference_solution: str
    existing_tests: List[str]
    raw: dict = field(default_factory=dict, repr=False)