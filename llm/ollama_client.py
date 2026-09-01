"""
Ollama client for the BDD generation pipeline.

This client intentionally uses urllib rather than requests to keep the
dependency surface small and preserve the original network behavior.
"""

import json
import os
import time
import urllib.error
import urllib.request
from typing import Optional

from dotenv import load_dotenv

from config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    OLLAMA_OPTIONS,
)

from llm.errors import OllamaError
from llm.response_extraction import extract_response_text


load_dotenv()


class OllamaClient:
    """
    Thin client for the Ollama generation API.

    Handles:
    - normal models,
    - thinking/reasoning models,
    - network errors,
    - timeout errors,
    - empty response errors.
    """

    def __init__(
        self,
        base_url: Optional[str] = OLLAMA_BASE_URL,
        model: str = OLLAMA_MODEL,
        timeout: int = OLLAMA_TIMEOUT,
        options: Optional[dict] = None,
    ):
        if not base_url:
            raise OllamaError(
                "OLLAMA_BASE_URL is not set. Check config.py or your .env file."
            )

        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

        # Preserves the original behavior where an empty dict also falls back
        # to the default options.
        self.options = options or OLLAMA_OPTIONS

        self._generate_url = f"{self.base_url}/api/generate"

    def generate(self, prompt: str) -> tuple[str, float]:
        """
        Send a prompt to the Ollama server.

        Returns:
            (response_text, elapsed_seconds)

        Raises:
            OllamaError for network, timeout, authentication, or empty-response
            failures.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": self.options,
        }

        api_key = os.getenv("OLLAMA_API_KEY")
        if not api_key:
            raise OllamaError(
                "OLLAMA_API_KEY is not set. Check your .env file."
            )

        body = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
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
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
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

        except (TimeoutError, ConnectionResetError, ConnectionAbortedError) as e:
            raise OllamaError(
                f"Connection timed out or was reset after {self.timeout}s: {e}\n"
                f"Options:\n"
                f"  1. Increase OLLAMA_TIMEOUT in config.py (currently {self.timeout}s)\n"
                f"  2. Run again with --resume to skip already-generated problems\n"
                f"  3. Reduce num_predict in OLLAMA_OPTIONS if the model is too slow"
            ) from e

        except OSError as e:
            raise OllamaError(
                f"Network/socket error communicating with Ollama server: {e}"
            ) from e

        text = extract_response_text(data)
        return text, elapsed

    def list_models(self) -> list[str]:
        """List models available on the Ollama server."""
        url = f"{self.base_url}/api/tags"
        req = urllib.request.Request(url, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m["name"] for m in data.get("models", [])]

        except Exception as e:
            raise OllamaError(f"Failed to list models: {e}") from e

    def ping(self) -> bool:
        """
        Check whether the configured model appears to be available.

        This does not generate a response. It only queries the model list.
        """
        try:
            models = self.list_models()
            exact = self.model in models
            prefix = [
                m
                for m in models
                if m.startswith(self.model.split(":")[0])
            ]

            if not exact and prefix:
                print(
                    f"[llm_client] Note: '{self.model}' not exact. "
                    f"Available matches: {prefix}"
                )

            elif not exact:
                print(
                    f"[llm_client] WARNING: '{self.model}' not found.\n"
                    f"Available: {models}\n"
                    "Update OLLAMA_MODEL in config.py."
                )

            return True

        except OllamaError:
            return False