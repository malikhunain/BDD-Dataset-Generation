class ParseError(Exception):
    pass

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
        # Try to detect which function the LLM actually generated
        import re as _re
        generated_fns = _re.findall(r'load_solution\(context\)\.([\w]+)', text)
        generated = generated_fns[0] if generated_fns else '(unknown)'
        raise ParseError(
            f"LLM generated '{generated}' but expected '{function_name}'. "
            f"The model hallucinated a different problem — dataset name removed from prompt."
        )
    try:
        compile(text, "<steps>", "exec")
    except SyntaxError as e:
        raise ParseError(f"Step definitions have a Python syntax error: {e}") from e
