"""Local AI via Ollama (http://127.0.0.1:11434). No models are bundled with
Arsenal; the user runs Ollama and pulls a model separately."""
from __future__ import annotations

from .provider import Provider, ProviderError, http_json


class OllamaProvider(Provider):
    name = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def available(self) -> bool:
        try:
            http_json(self.base_url + "/api/tags", timeout=4, method="GET")
            return True
        except ProviderError:
            return False

    def chat(self, messages: list[dict]) -> str:
        data = http_json(
            self.base_url + "/api/chat",
            {"model": self.model, "messages": messages, "stream": False},
            timeout=180,
        )
        return (data.get("message", {}) or {}).get("content", "").strip()
