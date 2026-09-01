import re

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

# Behave reserves these context attribute names for its own internal use.
_BEHAVE_RESERVED_ATTRS = {
    "text", "table", "failed", "stdout_capture", "stderr_capture",
    "log_capture", "feature", "scenario", "step",
}


def _fix_escape_sequences(text: str) -> str:
    """Convert step decorator string arguments with invalid escapes to raw strings."""
    def convert(m: re.Match) -> str:
        decorator = m.group(1)
        quote     = m.group(2)
        pattern   = m.group(3)
        if _INVALID_ESCAPE_RE.search(pattern):
            return f"@{decorator}(r{quote}{pattern}{quote})"
        return m.group(0)

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


def _fix_reserved_context_attrs(text: str) -> str:
    for attr in _BEHAVE_RESERVED_ATTRS:
        if f"context.{attr}" not in text:
            continue

        replacement = f"input_{attr}"

        # 1. Rename named capture groups: (?P<text>...) -> (?P<input_text>...)
        text = re.sub(
            rf"\(\?P<{attr}>",
            f"(?P<{replacement}>",
            text,
        )

        # 2. Rename function parameter in step def signatures: def step(context, text):
        #    Only rename the parameter, not arbitrary occurrences of the word
        text = re.sub(
            rf"(def\s+\w+\s*\(context\s*,\s*){attr}(\s*[\),])",
            rf"\g<1>{replacement}\2",
            text,
        )

        # 3. Rename context attribute usage: context.text -> context.input_text
        text = text.replace(f"context.{attr}", f"context.{replacement}")

        # 4. Rename bare variable references in step body that match the old param name
        #    e.g. `context.input_text = text` -> `context.input_text = input_text`
        #    Be careful: only rename standalone variable names, not substrings
        text = re.sub(
            rf"\bcontext\.{replacement}\s*=\s*{attr}\b",
            f"context.{replacement} = {replacement}",
            text,
        )

    return text


def _fix_mixed_matcher_syntax(text: str) -> str:
    is_regex_mode = (
        'use_step_matcher("re")' in text or
        "use_step_matcher('re')" in text
    )
    if not is_regex_mode:
        return text

    def replace_parse_placeholder(m: re.Match) -> str:
        decorator = m.group(1)
        quote     = m.group(2)
        pattern   = m.group(3)

        # Check if this pattern still has {param} style placeholders
        if not re.search(r'\{[a-zA-Z_]\w*\}', pattern):
            return m.group(0)  # no parse-style placeholders

        def to_regex_group(pm: re.Match) -> str:
            param_name = pm.group(1)
            return f"(?P<{param_name}>.*)"

        fixed_pattern = re.sub(r'\{([a-zA-Z_]\w*)\}', to_regex_group, pattern)
        return f"@{decorator}({quote}{fixed_pattern}{quote})"

    deco_re = re.compile(
        r"@(given|when|then|step)\((['\"])(.*?)\2\)",
        re.IGNORECASE,
    )
    return deco_re.sub(replace_parse_placeholder, text)


def _fix_wrong_function_name(text: str, expected_name: str) -> str:
    if expected_name in text:
        return text
    
    # Find all function names called via load_solution(context).<name>(
    generated_calls = re.findall(
        r'load_solution\(context\)\.(\w+)\s*\(',
        text,
    )
    if not generated_calls:
        return text

    unique_names = set(generated_calls)
    if len(unique_names) != 1:
        return text

    wrong_name = unique_names.pop()

    # Safety check: only rename if it looks like a naming variant
    def _same_operation(a: str, b: str) -> bool:
        """
        Return True if a and b likely name the same operation with different
        naming conventions (get_gcd vs find_gcd, isPalindrome vs is_palindrome).
        Strategy: strip common verb prefixes, normalise case and underscores,
        then check if the root operation names match or contain each other.
        """

        VERB_PREFIXES = (
            "get", "find", "is", "check", "has", "compute",
            "calc", "do", "run", "make", "build",
        )
        def _root(name: str) -> str:
            # camelCase -> flat lowercase
            n = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", name)
            n = n.lower().replace("_", "")
            for p in VERB_PREFIXES:
                if n.startswith(p) and len(n) > len(p):
                    return n[len(p):]
            return n

        ra, rb = _root(a), _root(b)
        return ra == rb or ra in rb or rb in ra

    if not _same_operation(wrong_name, expected_name):
        # Names describe different operations — fully hallucinated problem.
        # Don't silently rename; let it fail so temperature escalation retries.
        return text

    # Replace all occurrences of the wrong name with the expected name
    # Use word-boundary matching to avoid partial replacements
    fixed = re.sub(
        rf'\b{re.escape(wrong_name)}\b',
        expected_name,
        text,
    )
    return fixed


def _fix_steps(text: str, expected_function_name: str = "") -> str:
    """Apply all automatic fixers in order."""
    text = _fix_escape_sequences(text)
    text = _fix_load_solution(text)
    text = _fix_step_matcher(text)
    text = _fix_reserved_context_attrs(text)
    text = _fix_mixed_matcher_syntax(text)
    if expected_function_name:
        text = _fix_wrong_function_name(text, expected_function_name)
    return text