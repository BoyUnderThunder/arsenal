"""Arsenal platform CLI — argument parsing and subcommand dispatch.

Running ``arsenal`` with no subcommand prints the armory (backwards compatible
with the original bash command). All other behaviour lives in
``arsenal_cli.commands.*`` so new subcommands are a one-line registration.
"""
from __future__ import annotations

import argparse
import sys

from . import __version__, log, ui
from .commands import armory, doctor, reportbug

# subcommand name -> (handler, help text)
_COMMANDS = {
    "armory": (armory.run, "list the weapon registry (default)"),
    "doctor": (doctor.run, "system health & security diagnostics"),
    "reportbug": (reportbug.run, "create a redacted support bundle"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arsenal",
        description="Arsenal — white-hat security platform",
    )
    parser.add_argument("--version", action="version", version=f"arsenal {__version__}")
    parser.add_argument("--no-color", action="store_true", help="disable coloured output")
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose logging to stderr")

    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.add_parser("armory", help=_COMMANDS["armory"][1])
    sub.add_parser("doctor", help=_COMMANDS["doctor"][1])
    rb = sub.add_parser("reportbug", help=_COMMANDS["reportbug"][1])
    rb.add_argument("--no-redact", action="store_true", help="do not redact sensitive data")
    rb.add_argument("-o", "--output", help="output path for the bundle")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.no_color:
        ui.set_color(False)
    log.setup(verbose=args.verbose)

    command = args.command or "armory"
    handler = _COMMANDS.get(command, (None,))[0]
    if handler is None:
        parser.print_help()
        return 2

    try:
        return int(handler(args) or 0)
    except KeyboardInterrupt:
        print()
        return 130
    except Exception as exc:  # last-resort guard: log + friendly message
        log.get_logger("main").exception("command '%s' failed", command)
        ui.print_status(ui.Status.FAIL, f"arsenal {command} failed", str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
