import re
from typing import List, Optional


FUNCTION_NAME_RE = re.compile(r"def\s+(\w+)\s*\(")

# Legacy signature regex used by HumanEval and MBPP loaders.
LEGACY_SIGNATURE_RE = re.compile(
    r"(def\s+\w+\s*\(.*?\)\s*(?:->\s*\S+)?\s*):"
)

# Signature regex used by the new unified-format dataset loader.
UNIFIED_SIGNATURE_RE = re.compile(
    r"(def\s+\w+\s*\(.*?\)\s*(?:->\s*[\w\[\], ]+)?\s*):"
)


def extract_function_name(code: str) -> Optional[str]:
    match = FUNCTION_NAME_RE.search(code)
    return match.group(1) if match else None


def extract_legacy_signature(code: str, fallback_name: str) -> str:
    """
    Extract a function signature using the historical loader behavior.
    """
    match = LEGACY_SIGNATURE_RE.search(code)
    if match:
        return (match.group(0) + ":").strip()

    return f"def {fallback_name}(...):"


def extract_unified_signature(code: str, fallback_name: str) -> str:
    """
    Extract a function signature from the unified new_dataset.jsonl format.
    """
    match = UNIFIED_SIGNATURE_RE.search(code)
    if match:
        return match.group(0).strip()

    return f"def {fallback_name}(...):"