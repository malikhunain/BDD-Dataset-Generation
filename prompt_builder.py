"""
prompt_builder.py -- Builds the LLM generation prompt.

Design principles:
  1. Role + task framing first (establishes what the model IS)
  2. Hard rules numbered and grouped by category
  3. Two verified few-shot examples (HumanEval/0 and MBPP/11)
  4. Target problem last, with explicit "do not explain, just output" reminder
  5. Compact — minimises tokens consumed by thinking models
"""

from data_loader import ProblemRecord
from config import TARGET_SCENARIOS
import textwrap


# ── Few-shot Example 1 — HumanEval/0 ────────────────────────────────────────
# Boolean return, numeric input, uses default parse step matcher

_FEWSHOT_HE0_FEATURE = textwrap.dedent("""\
    Feature: Detecting close numbers in a list
      As a data validation system
      I want to check whether any two numbers in a list are closer than a threshold
      So that I can flag lists with suspiciously similar values

      Scenario: No two numbers are within the threshold
        Given a list of numbers [1.0, 2.0, 3.0]
        When I check for close elements with threshold 0.5
        Then the result should be False

      Scenario: Two numbers are within the threshold
        Given a list of numbers [1.0, 2.8, 3.0, 4.0, 5.0, 2.0]
        When I check for close elements with threshold 0.3
        Then the result should be True

      Scenario: Exact threshold boundary is not considered close
        Given a list of numbers [1.0, 2.0, 3.0]
        When I check for close elements with threshold 1.0
        Then the result should be False

      Scenario: Single element list has no pairs to compare
        Given a list of numbers [5.0]
        When I check for close elements with threshold 0.1
        Then the result should be False

      Scenario: Duplicate values have zero distance which is less than any positive threshold
        Given a list of numbers [1.0, 1.0, 2.0]
        When I check for close elements with threshold 0.001
        Then the result should be True""")

_FEWSHOT_HE0_STEPS = textwrap.dedent("""\
    import ast, importlib.util, os
    from behave import given, when, then

    def load_solution(context):
        path = context.config.userdata.get(
            "solution_path",
            os.path.join(os.path.dirname(__file__), "../../solution.py")
        )
        spec = importlib.util.spec_from_file_location("solution", path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    @given("a list of numbers {numbers}")
    def step_given(context, numbers):
        context.numbers = ast.literal_eval(numbers)

    @when("I check for close elements with threshold {threshold}")
    def step_when(context, threshold):
        context.result = load_solution(context).has_close_elements(
            context.numbers, float(threshold)
        )

    @then("the result should be {expected}")
    def step_then(context, expected):
        assert context.result == ast.literal_eval(expected), (
            f"Expected {expected}, got {context.result}"
        )""")


# ── Few-shot Example 2 — MBPP/11 ────────────────────────────────────────────
# String return, two Given steps, uses regex step matcher for quoted strings

_FEWSHOT_MBPP11_FEATURE = textwrap.dedent("""\
    Feature: Filtering characters from a string
      As a text processing utility
      I want to remove all characters from a source string that appear in a blacklist
      So that I can sanitize text against unwanted characters

      Scenario: Remove blacklisted characters from source
        Given a source string "probleesome"
        And a set of dirty characters "pro"
        When I remove dirty characters from the source
        Then the result should be "bleesme"

      Scenario: Non-blacklisted characters are preserved
        Given a source string "fight"
        And a set of dirty characters "ght"
        When I remove dirty characters from the source
        Then the result should be "fi"

      Scenario: Empty blacklist leaves source unchanged
        Given a source string "hello"
        And a set of dirty characters ""
        When I remove dirty characters from the source
        Then the result should be "hello"

      Scenario: All characters blacklisted produces empty string
        Given a source string "abc"
        And a set of dirty characters "abc"
        When I remove dirty characters from the source
        Then the result should be ""

      Scenario: Empty source string always returns empty string
        Given a source string ""
        And a set of dirty characters "abc"
        When I remove dirty characters from the source
        Then the result should be ""  """)

_FEWSHOT_MBPP11_STEPS = textwrap.dedent('''\
    import importlib.util, os
    from behave import given, when, then, use_step_matcher
    use_step_matcher("re")

    def load_solution(context):
        path = context.config.userdata.get(
            "solution_path",
            os.path.join(os.path.dirname(__file__), "../../solution.py")
        )
        spec = importlib.util.spec_from_file_location("solution", path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    @given(\'a source string "(?P<source>.*)"\')\

    def step_given_source(context, source):
        context.source = source

    @given(\'a set of dirty characters "(?P<dirty>.*)"\')\

    def step_given_dirty(context, dirty):
        context.dirty = dirty

    @when("I remove dirty characters from the source")
    def step_when(context):
        context.result = load_solution(context).remove_dirty_chars(
            context.source, context.dirty
        )

    @then(\'the result should be "(?P<expected>.*)"\')\

    def step_then(context, expected):
        assert context.result == expected, (
            f"Expected {expected!r}, got {context.result!r}"
        )''')


# ── System prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a senior Python test engineer with deep expertise in Behavior-Driven \
Development (BDD) and the Python Behave framework. You write precise, executable \
Gherkin feature files and Behave step definitions for algorithmic coding problems.

═══════════════════════════════════════════════════════
TASK
═══════════════════════════════════════════════════════
Given a Python function specification, produce:
  1. A Gherkin feature file  (.feature)
  2. Python Behave step definitions  (_steps.py)

These files will be executed automatically by Behave against the reference \
solution to validate correctness. Every scenario must pass.

═══════════════════════════════════════════════════════
SCENARIOS  (write exactly {n_scenarios})
═══════════════════════════════════════════════════════
- At least 2 normal/happy-path scenarios based on the provided examples
- Remaining scenarios must be DIFFERENT edge cases chosen from:
    empty input, single element, zero, negative numbers,
    duplicate values, boundary conditions, large values
- Each scenario title must be unique and descriptive
- Each scenario structure:
    Scenario: <unique descriptive title>
      Given <input setup>
      [And <additional input if function has multiple parameters>]
      When <call the function — one When per scenario>
      Then <assert the result — one Then per scenario>

═══════════════════════════════════════════════════════
CORRECTNESS  (most critical rule)
═══════════════════════════════════════════════════════
Before writing any "Then" step, MENTALLY TRACE the function logic on that input.
Common failure modes to avoid:
  - Float precision: 9.999 % 1.0 = 0.9990000000000006, NOT 0.999
    → For float results use math.isclose() in the step assertion, NOT ==
  - Off-by-one: check boundary conditions carefully
  - Wrong return type: a function returning a list cannot return True/False
  - Empty input: [], "", 0 may cause errors in the reference solution —
    only include such scenarios if the function clearly handles them

═══════════════════════════════════════════════════════
STEP DEFINITIONS — MANDATORY RULES
═══════════════════════════════════════════════════════
RULE S1 — load_solution() must be copied EXACTLY as shown in the examples.
  Use ONLY: importlib.util.spec_from_file_location + module_from_spec
  FORBIDDEN: __import__(), importlib.import_module(), module_from_load(),
             module_from_file_spec(), module_from_load_spec()

RULE S2 — Required imports (always include ALL of these):
  import ast, importlib.util, os
  from behave import given, when, then
  import math          ← add this when the function returns a float

RULE S3 — Parsing step parameters:
  - Lists/dicts/tuples: ALWAYS use ast.literal_eval(param)
    NEVER use split(",") or strip("[]") — these break on empty inputs
  - Booleans/None:      use ast.literal_eval(param)
  - Integers/floats:    use int(param) or float(param)
  - Strings (quoted in feature file): use use_step_matcher("re") +
    regex group (?P<name>.*) to correctly match empty strings

RULE S4 — Float assertions:
  When the function returns a float, use math.isclose() NOT ==
  Example: assert math.isclose(context.result, float(expected), rel_tol=1e-9)

RULE S5 — Step pattern consistency:
  The text in @given/@when/@then decorators must EXACTLY match the
  corresponding step text in the feature file — word for word.
  Mismatch = undefined step = Behave failure.

RULE S6 — use_step_matcher("re"):
  Use it when ANY step pattern contains quoted strings.
  It must appear at module level, BEFORE any step decorators.
  When using regex patterns, use (?P<name>.*) named groups.

RULE S7 — When step:
  Must call: load_solution(context).<function_name>(args)
  Store result as: context.result = ...

═══════════════════════════════════════════════════════
OUTPUT FORMAT  — CRITICAL
═══════════════════════════════════════════════════════
Output EXACTLY the two blocks below. Nothing else.
No explanation. No preamble. No markdown outside the blocks.
Do not describe what you are doing. Start immediately with ### FEATURE FILE.

### FEATURE FILE
```gherkin
<complete feature file>
```

### STEP DEFINITIONS
```python
<complete step definitions file>
```"""


# ── Public function ──────────────────────────────────────────────────────────

def build_prompt(problem: ProblemRecord) -> str:
    """Build the full generation prompt with system instructions + 2 examples + target."""

    system = _SYSTEM_PROMPT.format(n_scenarios=TARGET_SCENARIOS)

    examples = (
        "══════════════════════════════════════════════════════\n"
        "EXAMPLE 1 — HumanEval/0  (bool return, numeric params, default matcher)\n"
        "══════════════════════════════════════════════════════\n\n"
        "Function name : has_close_elements\n"
        "Signature     : def has_close_elements(numbers: List[float], threshold: float) -> bool:\n"
        "Description   : Check if any two numbers in the list are closer than the threshold.\n"
        "Examples      : has_close_elements([1.0, 2.0, 3.0], 0.5) -> False\n"
        "                has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3) -> True\n\n"
        "### FEATURE FILE\n"
        "```gherkin\n"
        + _FEWSHOT_HE0_FEATURE + "\n"
        "```\n\n"
        "### STEP DEFINITIONS\n"
        "```python\n"
        + _FEWSHOT_HE0_STEPS + "\n"
        "```\n\n"
        "══════════════════════════════════════════════════════\n"
        "EXAMPLE 2 — MBPP/11  (str return, two inputs, quoted strings, regex matcher)\n"
        "══════════════════════════════════════════════════════\n\n"
        "Function name : remove_dirty_chars\n"
        "Signature     : def remove_dirty_chars(string: str, second_string: str) -> str:\n"
        "Description   : Remove all characters from the first string that appear in the second.\n"
        "Examples      : remove_dirty_chars(\"probleesome\", \"pro\") -> \"bleesme\"\n"
        "                remove_dirty_chars(\"fight\", \"ght\") -> \"fi\"\n\n"
        "### FEATURE FILE\n"
        "```gherkin\n"
        + _FEWSHOT_MBPP11_FEATURE + "\n"
        "```\n\n"
        "### STEP DEFINITIONS\n"
        "```python\n"
        + _FEWSHOT_MBPP11_STEPS + "\n"
        "```\n\n"
        "══════════════════════════════════════════════════════"
    )


    # ── Docstring examples ────────────────────────────────────────────────────
    examples_str = "\n".join(f"  {e}" for e in problem.docstring_examples[:6])
    if not examples_str.strip():
        examples_str = "  (no examples provided — infer from function signature)"

    # ── Existing tests from dataset ───────────────────────────────────────────
    # These are the problem author's own assertions — the gold standard for what
    # inputs and outputs are correct. Scenarios MUST cover these inputs.
    if problem.existing_tests:
        tests_lines = "\n".join(f"  {t}" for t in problem.existing_tests[:8])
        tests_block = (
            "Existing tests from dataset "
            "(your scenarios MUST cover these inputs and expected values):\n"
            + tests_lines + "\n\n"
        )
    else:
        tests_block = ""

    # ── Reference solution ────────────────────────────────────────────────────
    # Use this to trace the logic and compute exact expected values.
    # DO NOT copy it into the feature file or step definitions.
    solution_lines = problem.reference_solution.strip().splitlines()
    solution_preview = "\n".join(solution_lines[:60])
    if len(solution_lines) > 60:
        solution_preview += "\n  # ... (truncated)"
    solution_block = (
        "Reference solution "
        "(trace this to verify expected values — do NOT copy into your output):\n"
        "```python\n"
        + solution_preview
        + "\n```\n\n"
    )

    target = (
        f"YOUR TASK — {problem.problem_id}\n\n"
        f"Function name : {problem.function_name}\n"
        f"Signature     : {problem.function_signature}\n"
        f"Description   : {problem.nl_description}\n\n"
        f"Examples from docstring:\n{examples_str}\n\n"
        f"{tests_block}"
        f"{solution_block}"
        f"Remember:\n"
        f"  - Trace the reference solution for EVERY expected value — wrong values are the #1 failure\n"
        f"  - Cover ALL inputs in Existing tests above, plus additional edge cases\n"
        f"  - Use math.isclose() if the function returns a float\n"
        f"  - Copy load_solution() EXACTLY as shown — no variations\n"
        f"  - Step patterns must match feature file text word for word\n"
        f"  - Output ONLY the two blocks. Start with ### FEATURE FILE now."
    )

    return f"{system}\n\n{examples}\n\n{target}"