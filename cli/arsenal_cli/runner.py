"""A safe, uniform wrapper around external commands.

Every shell-out in Arsenal goes through :func:`run` so that timeouts, missing
binaries and errors are handled consistently and logged, and so command output
is trivially mockable in unit tests.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from .log import get_logger

log = get_logger(__name__)


@dataclass
class Result:
    """Outcome of a command invocation."""

    cmd: list[str]
    returncode: int
    stdout: str
    stderr: str
    ok: bool
    timed_out: bool = False
    missing: bool = False


def which(name: str) -> str | None:
    """Absolute path to ``name`` on ``$PATH``, or ``None``."""
    return shutil.which(name)


def run(
    cmd: list[str],
    *,
    timeout: float = 60.0,
    check: bool = False,
    input_text: str | None = None,
    env: dict | None = None,
) -> Result:
    """Run ``cmd`` capturing output. Never raises for missing/timeout unless
    ``check`` is set; returns a :class:`Result` describing what happened."""
    log.debug("run: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_text,
            env=env,
        )
    except FileNotFoundError:
        log.warning("command not found: %s", cmd[0])
        if check:
            raise
        return Result(cmd, 127, "", f"{cmd[0]}: command not found", False, missing=True)
    except subprocess.TimeoutExpired as exc:
        log.warning("command timed out after %ss: %s", timeout, " ".join(cmd))
        if check:
            raise
        return Result(
            cmd,
            124,
            exc.stdout or "" if isinstance(exc.stdout, str) else "",
            (exc.stderr or "" if isinstance(exc.stderr, str) else "") + "\n[timed out]",
            False,
            timed_out=True,
        )

    result = Result(cmd, proc.returncode, proc.stdout, proc.stderr, proc.returncode == 0)
    if check and not result.ok:
        raise subprocess.CalledProcessError(proc.returncode, cmd, proc.stdout, proc.stderr)
    return result
