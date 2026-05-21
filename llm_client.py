"""
llm_client.py — Thin client for the university Ollama server.

Handles both standard models and thinking/reasoning models (qwen3-next,
deepseek-r1, etc.) which return output in a separate 'thinking' field.
"""

import json
import os
import time
import urllib.request
import urllib.error
from typing import Optional
from dotenv import load_dotenv

from config import (
    OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT,
    OLLAMA_OPTIONS, IS_THINKING_MODEL,
)


class OllamaClient:

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model:    str = OLLAMA_MODEL,
        timeout:  int = OLLAMA_TIMEOUT,
        options:  dict = None,
    ):
        self.base_url        = base_url.rstrip("/")
        self.model           = model
        self.timeout         = timeout
        self.options         = options or OLLAMA_OPTIONS
        self._generate_url   = f"{self.base_url}/api/generate"

    def generate(self, prompt: str) -> tuple[str, float]:
        """
        Send a prompt and return (response_text, elapsed_seconds).

        For thinking models the actual output is in data['response'].
        If response is empty (token budget exhausted by thinking chain),
        we fall back to extracting the last code blocks from data['thinking'].
        """
        payload = {
            "model":   self.model,
            "prompt":  prompt,
            "stream":  False,
            "options": self.options,
        }
        api_key = os.getenv('OLLAMA_API_KEY')

        body = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(
            self._generate_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw     = resp.read().decode("utf-8")
                data    = json.loads(raw)
                elapsed = time.time() - t0

        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            raise OllamaError(
                f"HTTP {e.code} from Ollama API: {e.reason}\n"
                f"Response body: {body_text[:400]}"
            ) from e

        except urllib.error.URLError as e:
            raise OllamaError(
                f"Cannot reach Ollama server at {self._generate_url}: {e.reason}\n"
                "Are you on the university network / VPN?"
            ) from e

        text = self._extract_text(data, elapsed)
        return text, elapsed

    def _extract_text(self, data: dict, elapsed: float) -> str:
        """
        Extract the usable response text from the Ollama API response dict.

        Ollama response fields:
          data['response']  — the model's actual output (always present)
          data['thinking']  — internal chain-of-thought (thinking models only)
          data['done_reason'] — 'stop' = normal, 'length' = token limit hit
        """
        response  = data.get("response", "").strip()
        thinking  = data.get("thinking", "").strip()
        done_reason = data.get("done_reason", "stop")

        # ── Case 1: normal output ─────────────────────────────────────────
        if response:
            return response

        # ── Case 2: thinking model ran out of tokens before writing response
        if done_reason == "length" and thinking:
            print(
                f"    [llm_client] WARNING: Token limit hit during thinking. "
                f"Thinking used {len(thinking.split())} words. "
                f"Attempting to extract output from thinking chain..."
            )
            extracted = _extract_from_thinking(thinking)
            if extracted:
                print(f"    [llm_client] Extracted {len(extracted)} chars from thinking chain.")
                return extracted
            # If extraction failed, increase num_predict in config.py
            raise OllamaError(
                "Token limit exhausted during thinking and no usable output found.\n"
                f"Thinking chain was {len(thinking)} chars long.\n"
                "Fix: increase 'num_predict' in config.py (try 16384) or switch to a\n"
                "non-thinking model. If the model supports it, set IS_THINKING_MODEL=False\n"
                "and add 'think: False' to OLLAMA_OPTIONS."
            )

        # ── Case 3: empty for unknown reason ─────────────────────────────
        raise OllamaError(
            f"Empty response from model. done_reason='{done_reason}'. "
            f"Full data keys: {list(data.keys())}"
        )

    def list_models(self) -> list[str]:
        url = f"{self.base_url}/api/tags"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            raise OllamaError(f"Failed to list models: {e}") from e

    def ping(self) -> bool:
        try:
            models = self.list_models()
            exact  = self.model in models
            prefix = [m for m in models if m.startswith(self.model.split(":")[0])]
            if not exact and prefix:
                print(
                    f"[llm_client] Note: '{self.model}' not exact. "
                    f"Available matches: {prefix}"
                )
            elif not exact:
                print(
                    f"[llm_client] WARNING: '{self.model}' not found.\n"
                    f"Available: {models}\nUpdate OLLAMA_MODEL in config.py."
                )
            return True
        except OllamaError:
            return False


# ── Thinking chain extractor ─────────────────────────────────────────────────

def _extract_from_thinking(thinking: str) -> Optional[str]:
    """
    When a thinking model runs out of tokens, the actual output never gets
    written. However, the thinking chain sometimes contains the answer
    embedded within it as the model was composing it.

    Look for the last occurrence of gherkin + python code blocks in the
    thinking text, which represents the model's most refined attempt.
    """
    import re

    # Find all gherkin blocks
    gherkin_blocks = re.findall(
        r"```(?:gherkin|feature)\s*\n(.*?)```",
        thinking,
        re.DOTALL | re.IGNORECASE,
    )
    # Find all python blocks
    python_blocks = re.findall(
        r"```(?:python|py)\s*\n(.*?)```",
        thinking,
        re.DOTALL | re.IGNORECASE,
    )

    if gherkin_blocks and python_blocks:
        # Take the last of each (most complete version)
        feature = gherkin_blocks[-1].strip()
        steps   = python_blocks[-1].strip()
        return (
            "### FEATURE FILE\n"
            f"```gherkin\n{feature}\n```\n\n"
            "### STEP DEFINITIONS\n"
            f"```python\n{steps}\n```"
        )

    return None


class OllamaError(Exception):
    pass