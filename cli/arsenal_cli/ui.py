"""Terminal UI helpers — Arsenal dark-theme colours, status badges, headers.

Colour is disabled automatically when stdout is not a TTY or when ``NO_COLOR``
is set, so output stays clean in pipes, logs and CI.
"""
from __future__ import annotations

import os
import sys
from enum import Enum

# --- palette (matches the bash armory: red accent, cyan tools, dim notes) ----
RED = "\033[1;31m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _initial_color() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("ARSENAL_NO_COLOR"):
        return False
    return sys.stdout.isatty()


_ENABLED = _initial_color()


def set_color(enabled: bool) -> None:
    """Force colour output on or off (used by ``--no-color``)."""
    global _ENABLED
    _ENABLED = enabled


def color_enabled() -> bool:
    return _ENABLED


def style(text: str, *codes: str) -> str:
    """Wrap ``text`` in ANSI ``codes`` when colour is enabled."""
    if not _ENABLED or not codes:
        return text
    return "".join(codes) + text + RESET


class Status(Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    INFO = "info"


_SYMBOL: dict[Status, tuple[str, str]] = {
    Status.OK: ("✓", GREEN),   # ✓
    Status.WARN: ("!", YELLOW),
    Status.FAIL: ("✗", RED),   # ✗
    Status.INFO: ("i", CYAN),
}

# Ordering used to compute the "worst" status across a set of checks.
SEVERITY: dict[Status, int] = {Status.OK: 0, Status.INFO: 0, Status.WARN: 1, Status.FAIL: 2}


def badge(status: Status) -> str:
    symbol, color = _SYMBOL[status]
    return style(f"[{symbol}]", color, BOLD)


def line(status: Status, msg: str, detail: str = "") -> str:
    out = f"{badge(status)} {msg}"
    if detail:
        out += "  " + style(detail, DIM)
    return out


def print_status(status: Status, msg: str, detail: str = "", *, file=sys.stdout) -> None:
    print(line(status, msg, detail), file=file)


def header(title: str) -> str:
    return style(f"━━ {title} ━━", RED, BOLD)
