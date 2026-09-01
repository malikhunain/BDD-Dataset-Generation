import textwrap

_FEWSHOT_HE55_FEATURE = textwrap.dedent("""\
    Feature: Fibonacci sequence lookup
      As a mathematical computation service
      I want to retrieve the n-th Fibonacci number
      So that clients can obtain sequence values without reimplementing the logic

      Scenario: Retrieve a mid-sequence Fibonacci value
        Given the position in the sequence is 10
        When the Fibonacci number at that position is requested
        Then the result should be 55

      Scenario: Retrieve the first Fibonacci value
        Given the position in the sequence is 1
        When the Fibonacci number at that position is requested
        Then the result should be 1

      Scenario: Retrieve the second Fibonacci value
        Given the position in the sequence is 2
        When the Fibonacci number at that position is requested
        Then the result should be 1

      Scenario: Sequence starts at zero for position zero
        Given the position in the sequence is 0
        When the Fibonacci number at that position is requested
        Then the result should be 0

      Scenario: Retrieve a larger Fibonacci value
        Given the position in the sequence is 20
        When the Fibonacci number at that position is requested
        Then the result should be 6765""")

_FEWSHOT_HE55_STEPS = textwrap.dedent("""\
    import ast, importlib.util, os
    from behave import given, when, then, use_step_matcher
    use_step_matcher("re")

    def load_solution(context):
        path = context.config.userdata.get(
            "solution_path",
            os.path.join(os.path.dirname(__file__), "../../solution.py")
        )
        spec = importlib.util.spec_from_file_location("solution", path)
        mod  = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            context._solution_load_error = str(e)
            return None
        return mod

    @given(r"the position in the sequence is (?P<n>\\d+)")
    def step_given_position(context, n):
        context.n = int(n)

    @when(r"the Fibonacci number at that position is requested")
    def step_when_fib(context):
        mod = load_solution(context)
        assert mod is not None, f"Solution failed to load: {context._solution_load_error}"
        context.result = mod.fib(context.n)

    @then(r"the result should be (?P<expected>-?\\d+)")
    def step_then_result(context, expected):
        assert context.result == int(expected), (
            f"Expected {expected}, got {context.result}"
        )""")

_FEWSHOT_HE7_FEATURE = textwrap.dedent("""\
    Feature: Filtering strings by substring presence
      As a search and filtering utility
      I want to keep only the strings that contain a given substring
      So that callers can narrow a list to relevant entries without manual iteration

      Scenario: Filter a mixed list keeping only matching strings
        Given a list of strings ["abc", "bacd", "xyz", "bcd"]
        And the substring to search for is "bc"
        When the list is filtered to retain only matching strings
        Then the result should be ["abc", "bacd", "bcd"]

      Scenario: No strings contain the substring
        Given a list of strings ["hello", "world"]
        And the substring to search for is "xyz"
        When the list is filtered to retain only matching strings
        Then the result should be []

      Scenario: All strings contain the substring
        Given a list of strings ["bc", "abc", "xbc"]
        And the substring to search for is "bc"
        When the list is filtered to retain only matching strings
        Then the result should be ["bc", "abc", "xbc"]

      Scenario: Empty input list produces empty output
        Given a list of strings []
        And the substring to search for is "a"
        When the list is filtered to retain only matching strings
        Then the result should be []

      Scenario: Single-character substring matches anywhere in string
        Given a list of strings ["apple", "pear", "cherry"]
        And the substring to search for is "a"
        When the list is filtered to retain only matching strings
        Then the result should be ["apple", "pear"]""")

_FEWSHOT_HE7_STEPS = textwrap.dedent('''\
    import ast, importlib.util, os
    from behave import given, when, then, use_step_matcher
    use_step_matcher("re")

    def load_solution(context):
        path = context.config.userdata.get(
            "solution_path",
            os.path.join(os.path.dirname(__file__), "../../solution.py")
        )
        spec = importlib.util.spec_from_file_location("solution", path)
        mod  = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            context._solution_load_error = str(e)
            return None
        return mod

    @given(r"a list of strings (?P<strings>\\[.*?\\])")
    def step_given_strings(context, strings):
        context.input_strings = ast.literal_eval(strings)

    @given(r\'the substring to search for is "(?P<substring>.*)"\')\

    def step_given_substring(context, substring):
        context.substring = substring

    @when(r"the list is filtered to retain only matching strings")
    def step_when_filter(context):
        mod = load_solution(context)
        assert mod is not None, f"Solution failed to load: {{context._solution_load_error}}"
        context.result = mod.filter_by_substring(context.input_strings, context.substring)

    @then(r"the result should be (?P<expected>\\[.*?\\])")
    def step_then_result(context, expected):
        assert context.result == ast.literal_eval(expected), (
            f"Expected {{expected}}, got {{context.result}}"
        )''')

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
SCENARIOS  (write minimum {n_scenarios} scenarios)
═══════════════════════════════════════════════════════
FEATURE HEADER — every feature file MUST start with this structure:
  Feature: <concise description of what the function does>
    As a <system or user role that benefits from this function>
    I want to <describe the desired behaviour in user terms>
    So that <describe the value or goal achieved>

SCENARIO STRUCTURE — each scenario must follow this format:
  Scenario: <unique, descriptive title explaining what is being tested>
    Given <input setup — one Given per input; use And for additional inputs>
    When  <describe what the system DOES in user/behaviour terms,
           NOT as a function call — e.g. "When the list is sorted by frequency"
           NOT "When I call sort_by_freq">
    Then  <assert the result — one Then per scenario>

SCENARIO COVERAGE:
  - At least 2 normal/happy-path scenarios based on the provided examples
  - Remaining scenarios must be DIFFERENT edge cases chosen from:
      Numeric inputs:  zero, negative numbers, boundary values, large values
      Collection inputs: empty input [], single element, duplicate values
      String inputs:   empty string "", single character, whitespace-only,
                       special characters, mixed case
      Composite:       mixed types in list, nested structures if applicable
  - Each scenario title must be unique and descriptive
  - Do NOT add a scenario for an edge case if the reference solution clearly
    does not handle it (e.g. do not test empty list if solution assumes len >= 1)

═══════════════════════════════════════════════════════
CORRECTNESS  (most critical — wrong expected values cause test failures)
═══════════════════════════════════════════════════════
STEP 1 — Before writing ANY "Then" step, MENTALLY TRACE the reference solution
  on that exact input and compute the expected output yourself.
  Wrong expected values are the #1 cause of failures. Do not guess.

STEP 2 — Watch for these common precision and type traps:
  - Float precision: 9.999 % 1.0 = 0.9990000000000006, NOT 0.999
    → Use math.isclose() for float results, never ==
  - Off-by-one: trace boundary conditions with care
  - Wrong return type: a function returning a list cannot produce True/False
  - None return: some functions return None (in-place operations) — assert
    context.result is None, not == None
  - Tuple return: assert context.result == ast.literal_eval(expected) where
    expected is written as "(1, 2)" in the feature file

═══════════════════════════════════════════════════════
STEP DEFINITIONS — MANDATORY RULES
═══════════════════════════════════════════════════════
RULE S1 — load_solution() MUST be copied EXACTLY as shown in the examples,
  including the try/except around exec_module.
  Use ONLY: importlib.util.spec_from_file_location + module_from_spec
  FORBIDDEN: __import__(), importlib.import_module(), module_from_load(),
             module_from_file_spec(), module_from_load_spec()

  The try/except is REQUIRED — without it, a syntax error in generated code
  will crash Behave with an unhandled exception instead of a clean FAILED step:

    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        context._solution_load_error = str(e)
        return None

  In every @when step, check the result immediately after calling load_solution:
    mod = load_solution(context)
    assert mod is not None, f"Solution failed to load: {{context._solution_load_error}}"

RULE S2 — Required imports (always include ALL of these):
  import ast, importlib.util, os
  from behave import given, when, then, use_step_matcher
  import math          ← add this when the function returns a float

RULE S3 — Parsing step parameters:
  - Lists/dicts/tuples: ALWAYS use ast.literal_eval(param)
    NEVER use split(",") or strip("[]") — these break on empty inputs
  - Booleans/None:      use ast.literal_eval(param)
  - Integers/floats:    use int(param) or float(param)
  - Strings (quoted in feature file): capture with regex group (?P<name>.*)
    so that empty strings "" are matched correctly (see Rule S6)

RULE S4 — Float assertions:
  When the function returns a float, use math.isclose() NOT ==
  Example: assert math.isclose(context.result, float(expected), rel_tol=1e-9)

RULE S5 — Step pattern consistency:
  The text in @given/@when/@then decorators must EXACTLY match the
  corresponding step text in the feature file — word for word.
  Mismatch = undefined step = Behave failure.

RULE S6 — use_step_matcher("re") — ALWAYS required:
  ALWAYS add these two lines at module level, BEFORE all decorators:
    from behave import given, when, then, use_step_matcher
    use_step_matcher("re")
  When active, ALL step patterns are treated as regular expressions. This means:
  - Use raw strings for all patterns: r"pattern here"
  - Use (?P<name>pattern) named groups for ALL parameter captures
  - NEVER use {{param}} parse-style syntax — it is a literal string in regex
    mode and will cause UNDEFINED STEP errors
  CORRECT:   @given(r"a list of numbers (?P<numbers>\\[.*?\\])")
  INCORRECT: @given("a list of numbers {{numbers}}")   # BROKEN in regex mode
  INCORRECT: @given("a list of numbers {{numbers}}")     # also broken

RULE S7 — None return types:
  When the function returns None (in-place operations, void-like functions):
  - Write the Then step as: Then the function should return nothing
  - Assert with: assert context.result is None, f"Expected None, got {{context.result}}"
  - Do NOT write: Then the result should be None  (fragile regex match)

RULE S8 — FORBIDDEN context attribute names:
  NEVER store step data in: context.text, context.table, context.feature,
  context.scenario, context.step, context.failed
  These are RESERVED by Behave and will be silently overwritten between steps,
  causing TypeError (NoneType is not subscriptable) in the When step.
  Use descriptive names: context.input_text, context.numbers, context.input_value

RULE S9 — When step:
  Must call: load_solution(context).<function_name>(args)
  Store result as: context.result = ...
  Always guard with: assert mod is not None before calling the function.

RULE S10 — Tuple return types:
  When the function returns a tuple:
  - Write the expected value in the feature file using Python tuple syntax: (1, 2)
  - Parse in the Then step with: ast.literal_eval(expected)
  - Assert with: assert context.result == ast.literal_eval(expected)
  Example Then step text:  Then the result should be (3, 4)
  Example assertion:       assert context.result == ast.literal_eval(expected)

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
