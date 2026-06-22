"""Small interactive helpers shared by commands that change the system.

Centralises the confirm / ``--yes`` / EOF handling so every mutating command
(``update``, ``profile``, …) behaves identically and the prompt copy lives in
one place.
"""
from __future__ import annotations

from . import ui


def confirm_or_exit(question: str, *, assume_yes: bool = False) -> int | None:
    """Ask a yes/no *question* before a potentially destructive action.

    Returns ``None`` when the caller should proceed (the user answered yes, or
    ``assume_yes`` was set). Otherwise returns the exit code the command should
    return immediately:

    * ``0`` — the user declined ("aborted").
    * ``1`` — no answer could be read (EOF / non-interactive without ``--yes``).
    """
    if assume_yes:
        return None
    try:
        answer = input(f"  {question} [y/N] ").strip().lower()
    except EOFError:
        ui.print_status(ui.Status.FAIL, "no confirmation (use --yes)")
        return 1
    if answer in ("y", "yes"):
        return None
    ui.print_status(ui.Status.INFO, "aborted")
    return 0
