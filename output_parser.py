"""
output_parser.py — Parses the LLM response into a feature file and step definitions.

The LLM is prompted to output exactly two fenced code blocks.
This module extracts them, applies automatic fixes for common LLM mistakes,
validates the results, and writes them to disk.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from data_loader import ProblemRecord
from config import GENERATED_DIR


@dataclass
class ParsedOutput:
    feature_content: str
    steps_content:   str
    feature_path:    Path
    steps_path:      Path
    solution_path:   Path


class ParseError(Exception):
    pass


# ── Extraction ───────────────────────────────────────────────────────────────

def _extract_blocks(raw: str):
    """
    Extract the gherkin and python fenced code blocks from the LLM response.
    Returns (feature_text, steps_text) or (None, None) if not found.
    Handles labelled/unlabelled blocks and ### section headers.
    """
    gherkin_pattern = re.compile(
        r"```(?:gherkin|feature|cucumber)\s*\n(.*?)```",
        re.DOTALL | re.IGNORECASE,
    )
    python_pattern = re.compile(
        r"```(?:python|py)\s*\n(.*?)```",
        re.DOTALL | re.IGNORECASE,
    )

    gherkin_matches = gherkin_pattern.findall(raw)
    python_matches  = python_pattern.findall(raw)

    if gherkin_matches and python_matches:
        return gherkin_matches[0].strip(), python_matches[0].strip()

    # Unlabelled blocks: identify by content
    any_block = re.compile(r"```\w*\s*\n(.*?)```", re.DOTALL)
    all_blocks = any_block.findall(raw)
    if len(all_blocks) >= 2:
        feature, steps = None, None
        for block in all_blocks[:4]:
            b = block.strip()
            if feature is None and ("Feature:" in b or "Scenario:" in b):
                feature = b
            elif steps is None and ("def " in b or "from behave" in b or "@given" in b.lower()):
                steps = b
        if feature and steps:
            return feature, steps

    # Section headers fallback
    feature_section = re.search(
        r"### FEATURE FILE.*?```\w*\s*\n(.*?)```",
        raw, re.DOTALL | re.IGNORECASE,
    )
    steps_section = re.search(
        r"### STEP DEFINITIONS.*?```\w*\s*\n(.*?)```",
        raw, re.DOTALL | re.IGNORECASE,
    )
    if feature_section and steps_section:
        return feature_section.group(1).strip(), steps_section.group(1).strip()

    return None, None


# ── Auto-fixers ───────────────────────────────────────────────────────────────
#
# These fix the two most common LLM mistakes we observed in testing:
#
# FAILURE MODE 1 — Invalid escape sequences (\d, \w, \s, etc.) in step
#   decorator strings. Python 3.12 raises SyntaxWarning and Behave silently
#   fails to register the step pattern -> "undefined steps" error.
#   Fix: convert the decorator string argument to a raw string (r'...').
#
# FAILURE MODE 2 — Broken load_solution() implementation. The LLM sometimes
#   ignores the template and writes __import__("solution") or similar shortcuts
#   that don't honour the solution_path userdata key.
#   Fix: replace the whole function body with the canonical importlib.util version.
#
# FAILURE MODE 3 — Missing use_step_matcher("re"). When a step uses regex
#   named groups like (?P<x>.*) but the file doesn't declare the regex matcher,
#   Behave defaults to the parse matcher and the pattern never matches.
#   Fix: insert use_step_matcher("re") after the last import line.

_INVALID_ESCAPE_RE = re.compile(r'\\[dwsDWSbBAZ1-9]')

_CANONICAL_LOAD_SOLUTION = (
    "def load_solution(context):\n"
    "    path = context.config.userdata.get(\n"
    '        "solution_path",\n'
    '        os.path.join(os.path.dirname(__file__), "../../solution.py")\n'
    "    )\n"
    '    spec = importlib.util.spec_from_file_location("solution", path)\n'
    "    mod  = importlib.util.module_from_spec(spec)\n"
    "    spec.loader.exec_module(mod)\n"
    "    return mod\n"
)


def _fix_escape_sequences(text: str) -> str:
    """Convert step decorator string arguments with invalid escapes to raw strings."""
    def convert(m: re.Match) -> str:
        decorator = m.group(1)
        quote     = m.group(2)
        pattern   = m.group(3)
        if _INVALID_ESCAPE_RE.search(pattern):
            return f"@{decorator}(r{quote}{pattern}{quote})"
        return m.group(0)

    # Match @given('...') @when("...") @then('...') — single or double quoted
    deco_re = re.compile(
        r"@(given|when|then|step)\((['\"])(.*?)\2\)",
        re.IGNORECASE,
    )
    return deco_re.sub(convert, text)


def _fix_load_solution(text: str) -> str:
    """Replace broken load_solution() implementations with the canonical version."""
    broken_patterns = ["__import__", "importlib.import_module"]
    has_broken  = any(p in text for p in broken_patterns)
    has_correct = "spec_from_file_location" in text

    if has_broken and not has_correct:
        text = re.sub(
            r"def load_solution\(context\):.*?(?=\n(?:def |\@|\Z))",
            _CANONICAL_LOAD_SOLUTION,
            text,
            flags=re.DOTALL,
        )
        if "import importlib.util" not in text and "import importlib" not in text:
            text = "import importlib.util\n" + text
        if "import os" not in text:
            text = "import os\n" + text

    return text


def _fix_step_matcher(text: str) -> str:
    """Insert use_step_matcher('re') if regex groups are used but matcher not declared."""
    has_regex  = "(?P<" in text
    has_call   = 'use_step_matcher("re")' in text or "use_step_matcher('re')" in text

    if has_regex and not has_call:
        lines = text.splitlines()
        last_import = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                last_import = i
        lines.insert(last_import + 1, '\nuse_step_matcher("re")\n')
        text = "\n".join(lines)

    return text


def _fix_steps(text: str) -> str:
    """Apply all automatic fixers in order. Returns the (possibly modified) text."""
    text = _fix_escape_sequences(text)
    text = _fix_load_solution(text)
    text = _fix_step_matcher(text)
    return text


# ── Validation ───────────────────────────────────────────────────────────────

def _validate_feature(text: str) -> None:
    if "Feature:" not in text:
        raise ParseError("Feature file missing 'Feature:' declaration")
    if "Scenario:" not in text:
        raise ParseError("Feature file has no 'Scenario:' blocks")
    if "Given " not in text and "When " not in text:
        raise ParseError("Feature file has no Given/When steps")


def _validate_steps(text: str, function_name: str) -> None:
    if "from behave import" not in text and "@given" not in text.lower():
        raise ParseError("Step definitions missing behave imports")
    if "def load_solution" not in text:
        raise ParseError("Step definitions missing load_solution() helper")
    if function_name not in text:
        raise ParseError(
            f"Step definitions don't call '{function_name}' — "
            "LLM may have used a different function name"
        )
    try:
        compile(text, "<steps>", "exec")
    except SyntaxError as e:
        raise ParseError(f"Step definitions have a Python syntax error: {e}") from e


# ── File writing ──────────────────────────────────────────────────────────────

def _problem_dir(problem: ProblemRecord) -> Path:
    safe_id = problem.problem_id.replace("/", "_")
    return GENERATED_DIR / safe_id


def write_solution(problem: ProblemRecord) -> Path:
    d = _problem_dir(problem)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "solution.py"
    path.write_text(problem.reference_solution, encoding="utf-8")
    return path


def parse_and_write(problem: ProblemRecord, raw_response: str) -> ParsedOutput:
    """
    Parse the LLM response, auto-fix common mistakes, validate, write to disk.
    Raises ParseError if parsing or validation fails.
    """
    feature_text, steps_text = _extract_blocks(raw_response)

    if feature_text is None:
        raise ParseError(
            "Could not extract a Gherkin feature block from LLM response. "
            f"Response starts with: {raw_response[:300]!r}"
        )
    if steps_text is None:
        raise ParseError(
            "Could not extract a Python step definitions block from LLM response."
        )

    _validate_feature(feature_text)

    # Apply automatic fixes BEFORE validation so fixable errors don't cause
    # unnecessary retries (which consume LLM API time)
    steps_text = _fix_steps(steps_text)

    _validate_steps(steps_text, problem.function_name)

    # Write files
    d       = _problem_dir(problem)
    steps_d = d / "features" / "steps"
    steps_d.mkdir(parents=True, exist_ok=True)

    feature_path  = d / "features" / f"{problem.function_name}.feature"
    steps_path    = steps_d / f"{problem.function_name}_steps.py"
    solution_path = write_solution(problem)

    feature_path.write_text(feature_text, encoding="utf-8")
    steps_path.write_text(steps_text,     encoding="utf-8")

    return ParsedOutput(
        feature_content=feature_text,
        steps_content=steps_text,
        feature_path=feature_path,
        steps_path=steps_path,
        solution_path=solution_path,
    )


def count_scenarios(feature_text: str) -> int:
    return len(re.findall(r"^\s*Scenario:", feature_text, re.MULTILINE))