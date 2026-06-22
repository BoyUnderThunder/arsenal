"""Logging setup for the Arsenal CLI.

Logs go to a rotating file under ``/var/log/arsenal`` when writable, falling
back to a per-user state dir or ``/tmp`` (so the CLI works for non-root users
and in sandboxes). Warnings and above are also echoed to stderr; ``--verbose``
lowers that threshold to DEBUG.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def _writable_log_dir() -> Path:
    candidates = [
        os.environ.get("ARSENAL_LOG_DIR"),
        "/var/log/arsenal",
        os.path.expanduser("~/.local/state/arsenal"),
        "/tmp/arsenal",
    ]
    for cand in candidates:
        if not cand:
            continue
        p = Path(cand)
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".write-test"
            probe.touch()
            probe.unlink()
            return p
        except OSError:
            continue
    return Path("/tmp")


def setup(verbose: bool = False) -> None:
    """Configure the ``arsenal`` logger hierarchy. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    root = logging.getLogger("arsenal")
    root.setLevel(logging.DEBUG)
    root.propagate = False

    try:
        fh = RotatingFileHandler(
            _writable_log_dir() / "arsenal.log", maxBytes=1_000_000, backupCount=3
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
        )
        root.addHandler(fh)
    except OSError:
        pass  # file logging is best-effort

    sh = logging.StreamHandler()
    sh.setLevel(logging.DEBUG if verbose else logging.WARNING)
    sh.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root.addHandler(sh)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``arsenal`` namespace."""
    return logging.getLogger("arsenal." + name.rsplit(".", 1)[-1])
