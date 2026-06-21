"""Runtime configuration and well-known filesystem locations for Arsenal.

Configuration is layered: built-in defaults, then ``/etc/arsenal/arsenal.conf``
(system), then ``~/.config/arsenal/arsenal.conf`` (per-user). Environment
variables override individual paths so the CLI is easy to test in isolation.
"""
from __future__ import annotations

import configparser
import os
from pathlib import Path

# --- Well-known paths (env-overridable for testing) --------------------------
SYSTEM_CONF = Path(os.environ.get("ARSENAL_CONF", "/etc/arsenal/arsenal.conf"))
USER_CONF = Path(os.path.expanduser("~/.config/arsenal/arsenal.conf"))

REGISTRY = Path(os.environ.get("ARSENAL_REGISTRY", "/usr/local/share/arsenal/registry"))
LOG_DIR = Path(os.environ.get("ARSENAL_LOG_DIR", "/var/log/arsenal"))
ENGAGEMENTS_DIR = Path(
    os.environ.get("ARSENAL_ENGAGEMENTS", os.path.expanduser("~/engagements"))
)

# --- Built-in defaults -------------------------------------------------------
DEFAULTS: dict[str, dict[str, str]] = {
    "arsenal": {"version": "rolling", "build_date": "", "channel": "rolling"},
    "ai": {
        "provider": "ollama",
        "model": "llama3",
        "base_url": "http://127.0.0.1:11434",
        "api_key_env": "ARSENAL_AI_KEY",
    },
}


def load() -> configparser.ConfigParser:
    """Return the merged configuration (defaults < system < user)."""
    cp = configparser.ConfigParser()
    cp.read_dict(DEFAULTS)
    for path in (SYSTEM_CONF, USER_CONF):
        try:
            if path.is_file():
                cp.read(path)
        except (OSError, configparser.Error):
            # A malformed or unreadable config must never crash the CLI.
            continue
    return cp
