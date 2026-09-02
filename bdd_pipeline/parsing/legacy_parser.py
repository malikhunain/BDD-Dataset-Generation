# """
# output_parser.py — Parses the LLM response into a feature file and step definitions.

# The LLM is prompted to output exactly two fenced code blocks.
# This module extracts them, applies automatic fixes for common LLM mistakes,
# validates the results, and writes them to disk.

# Known LLM failure modes fixed here:
#   1. Invalid escape sequences (backslash-d, backslash-w etc.) in step decorator strings
#   2. Broken load_solution() using __import__ instead of importlib.util
#   3. Missing use_step_matcher("re") when named groups are used
#   4. [NEW] context.text clobbered by Behave's reserved attribute
#   5. [NEW] Mixed matcher syntax: use_step_matcher("re") active but Then step
#      uses {param} parse-style capture instead of (?P<name>.*) regex capture
# """

# import re
# from dataclasses import dataclass
# from pathlib import Path
# from typing import Optional

# # We import these at function call time to avoid circular imports at module load
# # from data_loader import ProblemRecord
# # from config import GENERATED_DIR


# @dataclass
# class ParsedOutput:
#     feature_content: str
#     steps_content:   str
#     feature_path:    Path
#     steps_path:      Path
#     solution_path:   Path


# class ParseError(Exception):
#     pass


# # ── Extraction ────────────────────────────────────────────────────────────────

# def _extract_blocks(raw: str):
#     gherkin_pattern = re.compile(
#         r"```(?:gherkin|feature|cucumber)\s*\n(.*?)```",
#         re.DOTALL | re.IGNORECASE,
#     )
#     python_pattern = re.compile(
#         r"```(?:python|py)\s*\n(.*?)```",
#         re.DOTALL | re.IGNORECASE,
#     )

#     gherkin_matches = gherkin_pattern.findall(raw)
#     python_matches  = python_pattern.findall(raw)

#     if gherkin_matches and python_matches:
#         return gherkin_matches[0].strip(), python_matches[0].strip()

#     any_block = re.compile(r"```\w*\s*\n(.*?)```", re.DOTALL)
#     all_blocks = any_block.findall(raw)
#     if len(all_blocks) >= 2:
#         feature, steps = None, None
#         for block in all_blocks[:4]:
#             b = block.strip()
#             if feature is None and ("Feature:" in b or "Scenario:" in b):
#                 feature = b
#             elif steps is None and ("def " in b or "from behave" in b or "@given" in b.lower()):
#                 steps = b
#         if feature and steps:
#             return feature, steps

#     feature_section = re.search(
#         r"### FEATURE FILE.*?```\w*\s*\n(.*?)```",
#         raw, re.DOTALL | re.IGNORECASE,
#     )
#     steps_section = re.search(
#         r"### STEP DEFINITIONS.*?```\w*\s*\n(.*?)```",
#         raw, re.DOTALL | re.IGNORECASE,
#     )
#     if feature_section and steps_section:
#         return feature_section.group(1).strip(), steps_section.group(1).strip()

#     return None, None


# # ── Auto-fixers ───────────────────────────────────────────────────────────────

# _INVALID_ESCAPE_RE = re.compile(r'\\[dwsDWSbBAZ1-9]')

# _CANONICAL_LOAD_SOLUTION = (
#     "def load_solution(context):\n"
#     "    path = context.config.userdata.get(\n"
#     '        "solution_path",\n'
#     '        os.path.join(os.path.dirname(__file__), "../../solution.py")\n'
#     "    )\n"
#     '    spec = importlib.util.spec_from_file_location("solution", path)\n'
#     "    mod  = importlib.util.module_from_spec(spec)\n"
#     "    spec.loader.exec_module(mod)\n"
#     "    return mod\n"
# )

# # Behave reserves these context attribute names for its own internal use.
# # If step code writes to context.<reserved>, Behave emits ContextMaskWarning
# # and may silently reset the value to None between steps, breaking everything.
# # Full list from behave source: text, table, failed, stdout_capture, etc.
# _BEHAVE_RESERVED_ATTRS = {
#     "text", "table", "failed", "stdout_capture", "stderr_capture",
#     "log_capture", "feature", "scenario", "step",
# }


# def _fix_escape_sequences(text: str) -> str:
#     """Convert step decorator string arguments with invalid escapes to raw strings."""
#     def convert(m: re.Match) -> str:
#         decorator = m.group(1)
#         quote     = m.group(2)
#         pattern   = m.group(3)
#         if _INVALID_ESCAPE_RE.search(pattern):
#             return f"@{decorator}(r{quote}{pattern}{quote})"
#         return m.group(0)

#     deco_re = re.compile(
#         r"@(given|when|then|step)\((['\"])(.*?)\2\)",
#         re.IGNORECASE,
#     )
#     return deco_re.sub(convert, text)


# def _fix_load_solution(text: str) -> str:
#     """Replace broken load_solution() implementations with the canonical version."""
#     broken_patterns = ["__import__", "importlib.import_module"]
#     has_broken  = any(p in text for p in broken_patterns)
#     has_correct = "spec_from_file_location" in text

#     if has_broken and not has_correct:
#         text = re.sub(
#             r"def load_solution\(context\):.*?(?=\n(?:def |\@|\Z))",
#             _CANONICAL_LOAD_SOLUTION,
#             text,
#             flags=re.DOTALL,
#         )
#         if "import importlib.util" not in text and "import importlib" not in text:
#             text = "import importlib.util\n" + text
#         if "import os" not in text:
#             text = "import os\n" + text

#     return text


# def _fix_step_matcher(text: str) -> str:
#     """Insert use_step_matcher('re') if regex groups are used but matcher not declared."""
#     has_regex  = "(?P<" in text
#     has_call   = 'use_step_matcher("re")' in text or "use_step_matcher('re')" in text

#     if has_regex and not has_call:
#         lines = text.splitlines()
#         last_import = 0
#         for i, line in enumerate(lines):
#             if line.startswith("import ") or line.startswith("from "):
#                 last_import = i
#         lines.insert(last_import + 1, '\nuse_step_matcher("re")\n')
#         text = "\n".join(lines)

#     return text


# def _fix_reserved_context_attrs(text: str) -> str:
#     """
#     Fix BUG: LLM uses context.text (or other Behave-reserved attribute names)
#     to pass step data between steps.

#     Behave reserves 'text' for multi-line docstring step arguments. Writing
#     context.text = value triggers ContextMaskWarning and Behave resets it to
#     None before the next step runs, so the When step receives None instead of
#     the value set in Given.

#     Fix: rename every occurrence of context.<reserved> to context.input_<reserved>
#     in both the decorator parameter names and the body assignments.

#     Example:
#       @given('a text "(?P<text>.*)"')       ->  @given('a text "(?P<input_text>.*)"')
#       def step(context, text):              ->  def step(context, input_text):
#           context.text = text              ->      context.input_text = input_text
#     """
#     for attr in _BEHAVE_RESERVED_ATTRS:
#         if f"context.{attr}" not in text:
#             continue

#         replacement = f"input_{attr}"

#         # 1. Rename named capture groups: (?P<text>...) -> (?P<input_text>...)
#         text = re.sub(
#             rf"\(\?P<{attr}>",
#             f"(?P<{replacement}>",
#             text,
#         )

#         # 2. Rename function parameter in step def signatures: def step(context, text):
#         #    Only rename the parameter, not arbitrary occurrences of the word
#         text = re.sub(
#             rf"(def\s+\w+\s*\(context\s*,\s*){attr}(\s*[\),])",
#             rf"\g<1>{replacement}\2",
#             text,
#         )

#         # 3. Rename context attribute usage: context.text -> context.input_text
#         text = text.replace(f"context.{attr}", f"context.{replacement}")

#         # 4. Rename bare variable references in step body that match the old param name
#         #    e.g. `context.input_text = text` -> `context.input_text = input_text`
#         #    Be careful: only rename standalone variable names, not substrings
#         text = re.sub(
#             rf"\bcontext\.{replacement}\s*=\s*{attr}\b",
#             f"context.{replacement} = {replacement}",
#             text,
#         )

#     return text


# def _fix_mixed_matcher_syntax(text: str) -> str:
#     """
#     Fix BUG: use_step_matcher("re") is set at the top of the file, but one or
#     more step decorator patterns still use {param} parse-style syntax instead
#     of (?P<name>.*) regex syntax.

#     When regex matcher is active, {param} is treated as a literal string
#     (curly braces are special in regex), so Behave reports the step as
#     UNDEFINED even though the decorator exists.

#     Fix: when use_step_matcher("re") is present, convert any remaining
#     {param_name} placeholders in decorator strings to (?P<param_name>[^"]*) or
#     (?P<param_name>.*) depending on context (quoted strings vs unquoted).
#     """
#     is_regex_mode = (
#         'use_step_matcher("re")' in text or
#         "use_step_matcher('re')" in text
#     )
#     if not is_regex_mode:
#         return text

#     def replace_parse_placeholder(m: re.Match) -> str:
#         decorator = m.group(1)
#         quote     = m.group(2)
#         pattern   = m.group(3)

#         # Check if this pattern still has {param} style placeholders
#         if not re.search(r'\{[a-zA-Z_]\w*\}', pattern):
#             return m.group(0)  # no parse-style placeholders, leave unchanged

#         def to_regex_group(pm: re.Match) -> str:
#             param_name = pm.group(1)
#             return f"(?P<{param_name}>.*)"

#         fixed_pattern = re.sub(r'\{([a-zA-Z_]\w*)\}', to_regex_group, pattern)
#         return f"@{decorator}({quote}{fixed_pattern}{quote})"

#     deco_re = re.compile(
#         r"@(given|when|then|step)\((['\"])(.*?)\2\)",
#         re.IGNORECASE,
#     )
#     return deco_re.sub(replace_parse_placeholder, text)


# def _fix_wrong_function_name(text: str, expected_name: str) -> str:
#     """
#     Fix Sub-problem B: model generated the correct logic but used a synonym
#     function name (e.g. get_gcd instead of find_gcd, isPowerOfTwo instead
#     of is_Power_Of_Two).

#     Strategy: if expected_name is NOT in the text but there IS exactly one
#     load_solution(context).<something>() call, replace that name with
#     expected_name everywhere in the file.

#     We only do this when there is a single unique generated name — if the
#     model generated multiple different calls we leave it alone (too risky
#     to auto-fix ambiguous cases).
#     """
#     import re as _re

#     if expected_name in text:
#         return text  # already correct, nothing to do

#     # Find all function names called via load_solution(context).<name>(
#     generated_calls = _re.findall(
#         r'load_solution\(context\)\.(\w+)\s*\(',
#         text,
#     )
#     if not generated_calls:
#         return text  # no load_solution calls found, can't fix

#     unique_names = set(generated_calls)
#     if len(unique_names) != 1:
#         return text  # multiple different names — too ambiguous to auto-fix

#     wrong_name = unique_names.pop()

#     # Safety check: only rename if it looks like a naming variant, not a
#     # completely different concept. We check that the names share at least
#     # 40% of their characters (rough similarity heuristic).
#     def _same_operation(a: str, b: str) -> bool:
#         """
#         Return True if a and b likely name the same operation with different
#         naming conventions (get_gcd vs find_gcd, isPalindrome vs is_palindrome).
#         Strategy: strip common verb prefixes, normalise case and underscores,
#         then check if the root operation names match or contain each other.
#         """
#         import re as _re2
#         VERB_PREFIXES = (
#             "get", "find", "is", "check", "has", "compute",
#             "calc", "do", "run", "make", "build",
#         )
#         def _root(name: str) -> str:
#             # camelCase -> flat lowercase
#             n = _re2.sub(r"(?<=[a-z])(?=[A-Z])", "_", name)
#             n = n.lower().replace("_", "")
#             for p in VERB_PREFIXES:
#                 if n.startswith(p) and len(n) > len(p):
#                     return n[len(p):]
#             return n

#         ra, rb = _root(a), _root(b)
#         return ra == rb or ra in rb or rb in ra

#     if not _same_operation(wrong_name, expected_name):
#         # Names describe different operations — fully hallucinated problem.
#         # Don't silently rename; let it fail so temperature escalation retries.
#         return text

#     # Replace all occurrences of the wrong name with the expected name
#     # Use word-boundary matching to avoid partial replacements
#     fixed = _re.sub(
#         rf'\b{_re.escape(wrong_name)}\b',
#         expected_name,
#         text,
#     )
#     return fixed


# def _fix_steps(text: str, expected_function_name: str = "") -> str:
#     """Apply all automatic fixers in order."""
#     text = _fix_escape_sequences(text)
#     text = _fix_load_solution(text)
#     text = _fix_step_matcher(text)
#     text = _fix_reserved_context_attrs(text)
#     text = _fix_mixed_matcher_syntax(text)
#     if expected_function_name:
#         text = _fix_wrong_function_name(text, expected_function_name)
#     return text


# # ── Validation ────────────────────────────────────────────────────────────────

# def _validate_feature(text: str) -> None:
#     if "Feature:" not in text:
#         raise ParseError("Feature file missing 'Feature:' declaration")
#     if "Scenario:" not in text:
#         raise ParseError("Feature file has no 'Scenario:' blocks")
#     if "Given " not in text and "When " not in text:
#         raise ParseError("Feature file has no Given/When steps")


# def _validate_steps(text: str, function_name: str) -> None:
#     if "from behave import" not in text and "@given" not in text.lower():
#         raise ParseError("Step definitions missing behave imports")
#     if "def load_solution" not in text:
#         raise ParseError("Step definitions missing load_solution() helper")
#     if function_name not in text:
#         # Try to detect which function the LLM actually generated
#         import re as _re
#         generated_fns = _re.findall(r'load_solution\(context\)\.([\w]+)', text)
#         generated = generated_fns[0] if generated_fns else '(unknown)'
#         raise ParseError(
#             f"LLM generated '{generated}' but expected '{function_name}'. "
#             f"The model hallucinated a different problem — dataset name removed from prompt."
#         )
#     try:
#         compile(text, "<steps>", "exec")
#     except SyntaxError as e:
#         raise ParseError(f"Step definitions have a Python syntax error: {e}") from e


# # ── File writing ──────────────────────────────────────────────────────────────

# def _problem_dir(problem):
#     from config import GENERATED_DIR
#     safe_id = problem.problem_id.replace("/", "_")
#     return GENERATED_DIR / safe_id


# def write_solution(problem) -> Path:
#     d = _problem_dir(problem)
#     d.mkdir(parents=True, exist_ok=True)
#     path = d / "solution.py"
#     path.write_text(problem.reference_solution, encoding="utf-8")
#     return path


# def parse_and_write(problem, raw_response: str) -> ParsedOutput:
#     """
#     Parse the LLM response, auto-fix common mistakes, validate, write to disk.
#     Raises ParseError if parsing or validation fails after fixes.
#     """
#     feature_text, steps_text = _extract_blocks(raw_response)

#     if feature_text is None:
#         raise ParseError(
#             "Could not extract a Gherkin feature block from LLM response. "
#             f"Response starts with: {raw_response[:300]!r}"
#         )
#     if steps_text is None:
#         raise ParseError(
#             "Could not extract a Python step definitions block from LLM response."
#         )

#     _validate_feature(feature_text)
#     steps_text = _fix_steps(steps_text, expected_function_name=problem.function_name)
#     _validate_steps(steps_text, problem.function_name)

#     d       = _problem_dir(problem)
#     steps_d = d / "features" / "steps"
#     steps_d.mkdir(parents=True, exist_ok=True)

#     feature_path  = d / "features" / f"{problem.function_name}.feature"
#     steps_path    = steps_d / f"{problem.function_name}_steps.py"
#     solution_path = write_solution(problem)

#     feature_path.write_text(feature_text, encoding="utf-8")
#     steps_path.write_text(steps_text,     encoding="utf-8")

#     return ParsedOutput(
#         feature_content=feature_text,
#         steps_content=steps_text,
#         feature_path=feature_path,
#         steps_path=steps_path,
#         solution_path=solution_path,
#     )


# def count_scenarios(feature_text: str) -> int:
#     return len(re.findall(r"^\s*Scenario:", feature_text, re.MULTILINE))