from bdd_pipeline.signatures import (
    extract_function_signature,
    infer_function_name_from_steps,
)


def test_prefers_requested_function_over_helper():
    code = """
def helper(x):
    return x

def main_task(a, b):
    return helper(a) + helper(b)
"""

    signature = extract_function_signature(code, preferred_names="main_task")

    assert signature == "def main_task(a, b):"


def test_extracts_typed_signature():
    code = """
from typing import List

def has_close_elements(numbers: List[float], threshold: float) -> bool:
    return False
"""

    signature = extract_function_signature(
        code,
        preferred_names="has_close_elements",
    )

    assert signature == (
        "def has_close_elements(numbers: List[float], threshold: float) -> bool:"
    )


def test_falls_back_to_first_non_private_function():
    code = """
def _helper():
    return 1

def visible_function():
    return _helper()
"""

    signature = extract_function_signature(code)

    assert signature == "def visible_function():"


def test_falls_back_to_first_function_when_only_private_exists():
    code = """
def _private_helper():
    return 1
"""

    signature = extract_function_signature(code)

    assert signature == "def _private_helper():"


def test_returns_empty_string_when_no_function_exists():
    code = """
x = 1
y = 2
"""

    signature = extract_function_signature(code)

    assert signature == ""


def test_infer_function_name_from_steps_using_mod():
    steps_text = """
context.result = mod.has_close_elements(context.numbers, float(threshold))
"""

    assert infer_function_name_from_steps(steps_text) == "has_close_elements"


def test_infer_function_name_from_steps_using_load_solution():
    steps_text = """
context.result = load_solution(context).filter_by_substring(
    context.input_strings,
    context.substring,
)
"""

    assert infer_function_name_from_steps(steps_text) == "filter_by_substring"