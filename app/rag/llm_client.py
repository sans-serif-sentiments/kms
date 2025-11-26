"""LLM client abstraction (defaulting to Ollama)."""
from __future__ import annotations

import logging
from typing import Dict, Optional

import httpx

LOGGER = logging.getLogger(__name__)


class LLMClient:
    """Thin wrapper over Ollama's /api/generate endpoint."""

    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=60)

    def generate_answer(self, system_prompt: str, user_prompt: str, model_override: Optional[str] = None) -> str:
        payload = {
            "model": model_override or self.model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
        }
        try:
            response = self._client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network errors
            LOGGER.error("LLM call failed: %s", exc)
            raise
        data: Dict[str, str] = response.json()
        return data.get("response", "")


__all__ = ["LLMClient"]
