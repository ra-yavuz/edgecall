"""Thin client for an OpenAI-compatible chat endpoint.

edgecall does NOT host a model. It talks to any OpenAI-compatible
``/v1/chat/completions`` endpoint you already run: llama.cpp's server,
ollama, LM Studio, or a hydra-llm model server. We only ever send a tiny
menu prompt and read back a short text reply, so this client is small on
purpose: one method, no streaming, no tool-calling.

We deliberately do NOT use the OpenAI tools/function-calling API here.
Weak models on these stacks have unreliable native tool-call support; a
plain text menu reply ("0001") is the most robust thing such a model can
produce. See menu.py for the format.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx


class ModelError(RuntimeError):
    pass


@dataclass
class ModelClient:
    base_url: str  # e.g. http://localhost:11434/v1
    model: str  # model name the endpoint expects, e.g. "phi3"
    api_key: Optional[str] = None  # most local servers ignore this
    timeout: float = 60.0
    # Low temperature: we want a deterministic menu pick, not creativity.
    temperature: float = 0.0
    # The reply is just an id, so a tight cap keeps a rambling weak model
    # from wandering and keeps latency down.
    max_tokens: int = 16

    def choose(self, menu_prompt: str) -> str:
        """Send the menu prompt, return the model's raw text reply.

        Raises ModelError on transport or protocol failure. Parsing the
        reply into a decision is the caller's job (menu.parse_reply).
        """
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict request router. You only ever reply "
                        "with one option id from the menu and nothing else."
                    ),
                },
                {"role": "user", "content": menu_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise ModelError(f"request to {url} failed: {exc}") from exc

        if resp.status_code != 200:
            raise ModelError(
                f"endpoint returned HTTP {resp.status_code}: {resp.text[:300]}"
            )
        try:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ModelError(
                f"unexpected response shape from {url}: {resp.text[:300]}"
            ) from exc
