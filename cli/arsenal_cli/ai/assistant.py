"""High-level assistant helpers: system prompt and context builders that turn
user intent into provider chat messages."""
from __future__ import annotations

from .provider import Provider

SYSTEM_PROMPT = (
    "You are the Arsenal assistant, an expert guide to the Arsenal white-hat "
    "security operating system (Arch + BlackArch). You explain Arsenal commands "
    "(doctor, update, reportbug, recon/web/ad workflows, profiles, report), the "
    "bundled security tools and their 'weapon' aliases, logs and findings, and "
    "recommend safe workflows. Be concise and accurate. Always assume the user "
    "is an authorized professional, and remind them to stay within scope and the "
    "law when relevant."
)

MAX_CONTEXT = 6000


def ask(provider: Provider, prompt: str, context: str = "") -> str:
    user = f"{context.strip()}\n\n{prompt}".strip() if context else prompt
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
    return provider.chat(messages)


def tool_prompt(tool: str) -> str:
    return (
        f"Explain the security tool or command '{tool}' as used in Arsenal: what "
        "it does, when to use it, a safe example invocation, and key cautions."
    )


def log_prompt() -> str:
    return (
        "Explain the following logs/findings. Highlight anything notable or "
        "security-relevant and suggest concrete next steps."
    )


def truncate(text: str, limit: int = MAX_CONTEXT) -> str:
    return text if len(text) <= limit else text[:limit] + "\n…[truncated]"
