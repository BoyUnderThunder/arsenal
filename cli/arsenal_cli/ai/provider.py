"""AI provider abstraction.

A :class:`Provider` exposes ``available()`` and ``chat(messages)``. Concrete
providers (local Ollama, OpenAI-compatible API) live in sibling modules; the
:func:`get_provider` factory selects one from config so models/backends can be
swapped without touching the rest of the CLI.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from ..log import get_logger

log = get_logger(__name__)


class ProviderError(Exception):
    """Raised when an AI request fails."""


class Provider(ABC):
    name = "base"

    @abstractmethod
    def available(self) -> bool:
        """Cheap reachability/credential check."""

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        """Send chat messages, return the assistant's text reply."""


def http_json(url: str, payload: dict | None = None, headers: dict | None = None,
              timeout: float = 60.0, method: str = "POST") -> dict:
    """Minimal JSON HTTP helper (stdlib only)."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise ProviderError(str(exc)) from exc


def get_provider(cfg, provider: str | None = None, model: str | None = None) -> Provider:
    name = (provider or cfg.get("ai", "provider", fallback="ollama")).lower()
    model = model or cfg.get("ai", "model", fallback="llama3")
    base_url = cfg.get("ai", "base_url", fallback="http://127.0.0.1:11434")

    if name in ("openai", "api", "openai-compat"):
        from .openai_compat import OpenAICompatProvider

        key_env = cfg.get("ai", "api_key_env", fallback="ARSENAL_AI_KEY")
        # If base_url still points at the Ollama default, fall back to OpenAI's.
        if "11434" in base_url:
            base_url = "https://api.openai.com"
        return OpenAICompatProvider(base_url, model, os.environ.get(key_env, ""))

    from .ollama import OllamaProvider

    return OllamaProvider(base_url, model)
