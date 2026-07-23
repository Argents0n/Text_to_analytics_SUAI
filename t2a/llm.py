"""LLM adapter: one ``complete(system, user)`` behind two providers.

OpenRouter is the default (free-tier coder models, no local heat); Ollama is the
local fallback. Both speak an OpenAI-style chat shape, so the adapter is thin.
Config comes from the environment (see .env.example).
"""

from __future__ import annotations

import os

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMError(RuntimeError):
    pass


class LLM:
    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.provider = (provider or os.getenv("T2A_PROVIDER", "openrouter")).lower()
        self.timeout = timeout
        if self.provider == "openrouter":
            self.model = model or os.getenv("T2A_MODEL", "qwen/qwen-2.5-coder-32b-instruct:free")
            self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        elif self.provider == "ollama":
            self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
            self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        else:
            raise LLMError(f"Неизвестный провайдер: {self.provider}")

    def complete(self, system: str, user: str, temperature: float = 0.0) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        if self.provider == "openrouter":
            return self._openrouter(messages, temperature)
        return self._ollama(messages, temperature)

    def _openrouter(self, messages, temperature: float) -> str:
        if not self.api_key:
            raise LLMError("OPENROUTER_API_KEY не задан (см. .env.example).")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": messages, "temperature": temperature}
        try:
            r = httpx.post(OPENROUTER_URL, headers=headers, json=payload, timeout=self.timeout)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            raise LLMError(f"OpenRouter {e.response.status_code}: {e.response.text[:200]}") from e
        except (httpx.HTTPError, KeyError, IndexError) as e:
            raise LLMError(f"OpenRouter запрос не удался: {e}") from e

    def _ollama(self, messages, temperature: float) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        try:
            r = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
            r.raise_for_status()
            return r.json()["message"]["content"]
        except (httpx.HTTPError, KeyError) as e:
            raise LLMError(f"Ollama запрос не удался ({self.base_url}): {e}") from e
