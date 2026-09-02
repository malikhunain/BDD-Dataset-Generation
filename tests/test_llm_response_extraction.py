import pytest

from bdd_pipeline.llm.errors import OllamaError
from bdd_pipeline.llm.response_extraction import (
    extract_from_thinking,
    extract_response_text,
)


def test_normal_response_is_returned():
    data = {
        "response": "### FEATURE FILE\nok",
        "done_reason": "stop",
    }

    assert extract_response_text(data) == "### FEATURE FILE\nok"


def test_inline_think_blocks_are_removed():
    data = {
        "response": "<think>hidden reasoning</think>FINAL OUTPUT",
        "done_reason": "stop",
    }

    assert extract_response_text(data) == "FINAL OUTPUT"


def test_length_limit_falls_back_to_thinking_blocks():
    thinking = (
        "Some reasoning here.\n"
        "```gherkin\n"
        "Feature: Example feature\n"
        "```\n"
        "More reasoning.\n"
        "```python\n"
        "print('steps')\n"
        "```"
    )

    data = {
        "response": "",
        "done_reason": "length",
        "thinking": thinking,
    }

    expected = (
        "### FEATURE FILE\n"
        "```gherkin\n"
        "Feature: Example feature\n"
        "```\n\n"
        "### STEP DEFINITIONS\n"
        "```python\n"
        "print('steps')\n"
        "```"
    )

    assert extract_response_text(data) == expected


def test_length_limit_without_blocks_raises():
    data = {
        "response": "",
        "done_reason": "length",
        "thinking": "No code blocks here.",
    }

    with pytest.raises(OllamaError):
        extract_response_text(data)


def test_empty_response_raises():
    data = {
        "response": "",
        "done_reason": "stop",
    }

    with pytest.raises(OllamaError):
        extract_response_text(data)


def test_extract_from_thinking_uses_last_blocks():
    thinking = (
        "```gherkin\n"
        "Feature: First\n"
        "```\n"
        "```python\n"
        "first = 1\n"
        "```\n"
        "```gherkin\n"
        "Feature: Second\n"
        "```\n"
        "```python\n"
        "second = 2\n"
        "```"
    )

    expected = (
        "### FEATURE FILE\n"
        "```gherkin\n"
        "Feature: Second\n"
        "```\n\n"
        "### STEP DEFINITIONS\n"
        "```python\n"
        "second = 2\n"
        "```"
    )

    assert extract_from_thinking(thinking) == expected
