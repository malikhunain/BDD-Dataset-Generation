"""
Response extraction utilities for Ollama responses.
"""

import re
from typing import Optional

from bdd_pipeline.llm.errors import OllamaError


_THINK_BLOCK_RE = re.compile(
    r"<think>.*?</think>",
    re.DOTALL,
)

_FEATURE_BLOCK_RE = re.compile(
    r"```(?:gherkin|feature)\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

_PYTHON_BLOCK_RE = re.compile(
    r"```(?:python|py)\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def strip_thinking_blocks(text: str) -> str:
    """
    Remove inline <think>...</think> blocks from model output.

    This is used for Qwen-style thinking outputs where the final response may
    still contain internal reasoning blocks.
    """
    if "<think>" in text:
        return _THINK_BLOCK_RE.sub("", text).strip()

    return text


def extract_from_thinking(thinking: str) -> Optional[str]:
    """
    Extract the last Gherkin and Python code blocks from a thinking chain.

    This fallback is used when a thinking model reaches the token limit before
    writing the final response field.
    """
    gherkin_blocks = _FEATURE_BLOCK_RE.findall(thinking)
    python_blocks = _PYTHON_BLOCK_RE.findall(thinking)

    if gherkin_blocks and python_blocks:
        feature = gherkin_blocks[-1].strip()
        steps = python_blocks[-1].strip()

        return (
            "### FEATURE FILE\n"
            f"```gherkin\n{feature}\n```\n\n"
            "### STEP DEFINITIONS\n"
            f"```python\n{steps}\n```"
        )

    return None


def extract_response_text(data: dict) -> str:
    """
    Extract usable response text from an Ollama API response dictionary.

    Ollama response fields:
        data["response"]    — final model output
        data["thinking"]    — internal chain-of-thought, for thinking models
        data["done_reason"] — "stop" for normal completion, "length" for token limit
    """
    response = data.get("response", "").strip()
    thinking = data.get("thinking", "").strip()
    done_reason = data.get("done_reason", "stop")

    response = strip_thinking_blocks(response)

    if response:
        return response

    if done_reason == "length" and thinking:
        print(
            f"    [llm_client] WARNING: Token limit hit during thinking. "
            f"Thinking used {len(thinking.split())} words. "
            f"Attempting to extract output from thinking chain..."
        )

        extracted = extract_from_thinking(thinking)

        if extracted:
            print(
                f"    [llm_client] Extracted {len(extracted)} chars "
                "from thinking chain."
            )
            return extracted

        raise OllamaError(
            "Token limit exhausted during thinking and no usable output found.\n"
            f"Thinking chain was {len(thinking)} chars long.\n"
            "Fix: increase 'num_predict' in config.py (try 16384) or switch to a\n"
            "non-thinking model. If the model supports it, set IS_THINKING_MODEL=False\n"
            "and add 'think: False' to OLLAMA_OPTIONS."
        )

    raise OllamaError(
        f"Empty response from model. done_reason='{done_reason}'. "
        f"Full data keys: {list(data.keys())}"
    )