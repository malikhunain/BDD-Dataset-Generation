"""
Prompt construction for BDD feature and step generation.

This module assembles the final LLM prompt from:
- the frozen system prompt,
- frozen few-shot examples,
- the target problem record.
"""

from config import TARGET_SCENARIOS

from records import ProblemRecord
from prompts.assets import (
    _SYSTEM_PROMPT,
    _FEWSHOT_HE55_FEATURE,
    _FEWSHOT_HE55_STEPS,
    _FEWSHOT_HE7_FEATURE,
    _FEWSHOT_HE7_STEPS,
)


DOCSTRING_EXAMPLE_LIMIT = 6
EXISTING_TEST_LIMIT = 8
REFERENCE_SOLUTION_LINE_LIMIT = 60


def _build_examples_block() -> str:
    """
    Build the frozen few-shot examples block.
    """
    return (
        "══════════════════════════════════════════════════════\n"
        "EXAMPLE 1 — int return, single numeric param, regex matcher, behavioral When\n"
        "══════════════════════════════════════════════════════\n\n"
        "Function name : fib\n"
        "Signature     : def fib(n: int) -> int:\n"
        "Description   : Return the n-th Fibonacci number (0-indexed: fib(0)=0, fib(1)=1).\n"
        "Examples      : fib(10) -> 55\n"
        "                fib(1)  -> 1\n\n"
        "### FEATURE FILE\n"
        "```gherkin\n"
        + _FEWSHOT_HE55_FEATURE + "\n"
        "```\n\n"
        "### STEP DEFINITIONS\n"
        "```python\n"
        + _FEWSHOT_HE55_STEPS + "\n"
        "```\n\n"
        "══════════════════════════════════════════════════════\n"
        "EXAMPLE 2 — list[str] return, two params (list + quoted string), ast.literal_eval, regex matcher\n"
        "══════════════════════════════════════════════════════\n\n"
        "Function name : filter_by_substring\n"
        "Signature     : def filter_by_substring(strings: List[str], substring: str) -> List[str]:\n"
        "Description   : Filter an input list to only those strings containing the given substring.\n"
        "Examples      : filter_by_substring([\"abc\", \"bacd\", \"xyz\"], \"bc\") -> [\"abc\", \"bacd\"]\n"
        "                filter_by_substring([\"hello\", \"world\"], \"xyz\")    -> []\n\n"
        "### FEATURE FILE\n"
        "```gherkin\n"
        + _FEWSHOT_HE7_FEATURE + "\n"
        "```\n\n"
        "### STEP DEFINITIONS\n"
        "```python\n"
        + _FEWSHOT_HE7_STEPS + "\n"
        "```\n\n"
        "══════════════════════════════════════════════════════"
    )


def _build_docstring_examples_block(problem: ProblemRecord) -> str:
    """
    Build the target problem's docstring/example block.
    """
    examples_str = "\n".join(
        f"  {example}"
        for example in problem.docstring_examples[:DOCSTRING_EXAMPLE_LIMIT]
    )

    if not examples_str.strip():
        return "  (no examples provided — infer from function signature)"

    return examples_str


def _build_existing_tests_block(problem: ProblemRecord) -> str:
    """
    Build the block containing existing tests from the source dataset.
    """
    if not problem.existing_tests:
        return ""

    tests_lines = "\n".join(
        f"  {test}"
        for test in problem.existing_tests[:EXISTING_TEST_LIMIT]
    )

    return (
        "Existing tests from dataset "
        "(your scenarios MUST cover these inputs and expected values):\n"
        + tests_lines + "\n\n"
    )


def _build_reference_solution_block(problem: ProblemRecord) -> str:
    """
    Build the truncated reference-solution block used by the prompt.
    """
    solution_lines = problem.reference_solution.strip().splitlines()
    solution_preview = "\n".join(solution_lines[:REFERENCE_SOLUTION_LINE_LIMIT])

    if len(solution_lines) > REFERENCE_SOLUTION_LINE_LIMIT:
        solution_preview += "\n  # ... (truncated)"

    return (
        "Reference solution "
        "(trace this to verify expected values — do NOT copy into your output):\n"
        "```python\n"
        + solution_preview
        + "\n```\n\n"
    )


def _build_target_block(
    problem: ProblemRecord,
    examples_str: str,
    tests_block: str,
    solution_block: str,
) -> str:
    """
    Build the final target-task block.
    """
    return (
        f"YOUR TASK\n\n"
        f">>> TARGET FUNCTION: {problem.function_name} — generate BDD spec for THIS function only <<<\n\n"
        f"Function name : {problem.function_name}\n"
        f"Signature     : {problem.function_signature}\n"
        f"Description   : {problem.nl_description}\n\n"
        f"Examples from docstring:\n{examples_str}\n\n"
        f"{tests_block}"
        f"{solution_block}"
        f"Checklist before you output:\n"
        f"  1. TRACE the reference solution for EVERY expected value — wrong values = test failure\n"
        f"  2. Feature header has 'As a / I want / So that' narrative\n"
        f"  3. When steps describe behaviour, not function calls\n"
        f"  4. use_step_matcher(\"re\") is at the top of step definitions\n"
        f"  5. All decorators use raw strings r\"...\" with (?P<name>...) groups\n"
        f"  6. load_solution() includes try/except and @when checks mod is not None\n"
        f"  7. No reserved context attribute names (text, table, feature, scenario, step, failed)\n"
        f"  8. Step decorator text matches feature file text word for word\n"
        f"  9. Output ONLY the two blocks. Start with ### FEATURE FILE now."
    )


def build_prompt(problem: ProblemRecord) -> str:
    """
    Build the full generation prompt.

    The final prompt format is:
        system prompt
        few-shot examples
        target problem
    """
    system = _SYSTEM_PROMPT.format(n_scenarios=TARGET_SCENARIOS)
    examples = _build_examples_block()

    examples_str = _build_docstring_examples_block(problem)
    tests_block = _build_existing_tests_block(problem)
    solution_block = _build_reference_solution_block(problem)

    target = _build_target_block(
        problem=problem,
        examples_str=examples_str,
        tests_block=tests_block,
        solution_block=solution_block,
    )

    return f"{system}\n\n{examples}\n\n{target}"