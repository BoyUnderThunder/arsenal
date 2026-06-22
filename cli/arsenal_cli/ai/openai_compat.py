"""AI via any OpenAI-compatible chat-completions API (OpenAI, local gateways,
etc.). The API key is read from an environment variable (never bundled)."""
from __future__ import annotations

from .provider import Provider, ProviderError, http_json


class OpenAICompatProvider(Provider):
    name = "openai"

    def __init__(self, base_url: str, model: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    def available(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: list[dict]) -> str:
        data = http_json(
            self.base_url + "/v1/chat/completions",
            {"model": self.model, "messages": messages},
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=180,
        )
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"unexpected API response: {exc}") from exc
