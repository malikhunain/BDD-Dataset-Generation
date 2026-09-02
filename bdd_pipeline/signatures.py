"""
Function-signature extraction utilities.

This module extracts a clean function signature from Python source code.

It prefers the expected problem function name, because the first function in a
solution may be a helper function.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from typing import Iterable, List, Optional, Union


_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)

_LOAD_SOLUTION_CALL_RE = re.compile(
    r"load_solution\(context\)\s*\.\s*(\w+)\s*\("
)

_MOD_CALL_RE = re.compile(
    r"\bmod\s*\.\s*(\w+)\s*\("
)


def infer_function_name_from_steps(steps_text: str) -> Optional[str]:
    """
    Infer the target function name from Behave step definitions.

    Generated steps usually call the reference solution like:

        mod.has_close_elements(...)

    or:

        load_solution(context).has_close_elements(...)
    """
    if not steps_text:
        return None

    names = _LOAD_SOLUTION_CALL_RE.findall(steps_text)

    if not names:
        names = _MOD_CALL_RE.findall(steps_text)

    if not names:
        return None

    return Counter(names).most_common(1)[0][0]


def _normalise_preferred_names(
    preferred_names: Union[str, Iterable[str], None],
) -> List[str]:
    if preferred_names is None:
        return []

    if isinstance(preferred_names, str):
        return [preferred_names] if preferred_names else []

    return [name for name in preferred_names if name]


def _top_level_functions(tree: ast.AST):
    return [
        node
        for node in tree.body
        if isinstance(node, _FUNCTION_NODES)
    ]


def _select_function_node(
    tree: ast.AST,
    preferred_names: List[str],
):
    """
    Select the function node whose signature should be extracted.

    Selection priority:
      1. Top-level function matching a preferred name
      2. Any nested function matching a preferred name
      3. First top-level non-private function
      4. First top-level function
      5. First function anywhere
    """
    top_level = _top_level_functions(tree)

    for name in preferred_names:
        for node in top_level:
            if node.name == name:
                return node

    for name in preferred_names:
        for node in ast.walk(tree):
            if isinstance(node, _FUNCTION_NODES) and node.name == name:
                return node

    non_private_top_level = [
        node
        for node in top_level
        if not node.name.startswith("_")
    ]

    if non_private_top_level:
        return non_private_top_level[0]

    if top_level:
        return top_level[0]

    for node in ast.walk(tree):
        if isinstance(node, _FUNCTION_NODES):
            return node

    return None


def _signature_from_ast_node(node) -> Optional[str]:
    """
    Build a normalized signature from an AST function node.

    Example output:

        def has_close_elements(numbers: List[float], threshold: float) -> bool:
    """
    try:
        dummy_class = type(node)

        dummy = dummy_class(
            name=node.name,
            args=node.args,
            body=[ast.Pass()],
            decorator_list=[],
            returns=node.returns,
        )

        ast.fix_missing_locations(dummy)

        text = ast.unparse(dummy)
        return text.splitlines()[0].strip()

    except Exception:
        return None


def _signature_from_regex(
    source_code: str,
    preferred_names: List[str],
) -> str:
    """
    Regex fallback for source code that cannot be parsed by ast.
    """
    for name in preferred_names:
        pattern = re.compile(
            rf"(def\s+{re.escape(name)}\s*\([^)]*\)\s*(?:->\s*[^:]+)?):",
            re.DOTALL,
        )

        match = pattern.search(source_code)
        if match:
            return match.group(1).strip()

    match = re.search(
        r"(def\s+\w+\s*\([^)]*\)\s*(?:->\s*[^:]+)?):",
        source_code,
        re.DOTALL,
    )

    return match.group(1).strip() if match else ""


def extract_function_signature(
    source_code: str,
    preferred_names: Union[str, Iterable[str], None] = None,
) -> str:
    """
    Extract a clean function signature from Python source code.

    If preferred_names are provided, the extractor tries to find one of those
    functions first. This avoids accidentally returning a helper function.
    """
    if not source_code or not source_code.strip():
        return ""

    names = _normalise_preferred_names(preferred_names)

    try:
        tree = ast.parse(source_code)
        node = _select_function_node(tree, names)

        if node is not None:
            signature = _signature_from_ast_node(node)
            if signature:
                return signature

    except Exception:
        pass

    return _signature_from_regex(source_code, names)