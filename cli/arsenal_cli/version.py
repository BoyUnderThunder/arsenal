"""Resolve the Arsenal OS version for display.

Order of preference:
1. ``[arsenal] version`` / ``build_date`` from the merged config (build.sh
   stamps ``build_date`` at ISO build time).
2. ``BUILD_ID`` / ``VERSION_ID`` from ``/etc/os-release``.
3. The literal ``"rolling"``.
"""
from __future__ import annotations

from pathlib import Path

from . import __version__ as _CLI_VERSION
from .config import load


def cli_version() -> str:
    """Version of the arsenal CLI package."""
    return _CLI_VERSION


def os_version() -> str:
    """Best-effort human-readable Arsenal OS version."""
    cp = load()
    version = cp.get("arsenal", "version", fallback="rolling")
    build_date = cp.get("arsenal", "build_date", fallback="")
    suffix = f" ({build_date})" if build_date else ""

    if version and version != "rolling":
        return f"{version}{suffix}"

    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            for key in ("BUILD_ID=", "VERSION_ID="):
                if line.startswith(key):
                    val = line.split("=", 1)[1].strip().strip('"')
                    if val:
                        return f"{val}{suffix}"
    except OSError:
        pass
    return f"rolling{suffix}"
