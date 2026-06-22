"""Arsenal AI assistant: provider abstraction (Ollama / OpenAI-compatible)."""

from .provider import Provider, ProviderError, get_provider

__all__ = ["Provider", "ProviderError", "get_provider"]
