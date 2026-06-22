"""Top-level workflow commands: ``arsenal recon|web|ad <target>``.

Each wires CLI args to a :class:`Workflow` and enforces an authorization
confirmation before launching active tooling.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .. import ui
from ..workflows.ad import ADWorkflow
from ..workflows.recon import ReconWorkflow
from ..workflows.web import WebWorkflow


def _authorized(target: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        ui.print_status(
            ui.Status.FAIL,
            "refusing to launch active testing without confirmation",
            "pass --yes for non-interactive use",
            file=sys.stderr,
        )
        return False
    print(ui.style(f"⚠ Active testing against: {target}", ui.YELLOW, ui.BOLD))
    print("  Only proceed against systems you are explicitly authorized to test.")
    try:
        answer = input("  Proceed? [y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def _base(args) -> Path | None:
    out = getattr(args, "output", None)
    return Path(out) if out else None


def _common_args(parser) -> None:
    parser.add_argument("-y", "--yes", action="store_true", help="skip the authorization prompt")
    parser.add_argument("--dry-run", action="store_true", help="print the plan without running")
    parser.add_argument("--name", help="project name")
    parser.add_argument("-o", "--output", help="base directory for the engagement project")


# --- recon -------------------------------------------------------------------
def add_recon_args(parser) -> None:
    parser.add_argument("target", help="host, IP/CIDR or URL")
    parser.add_argument("--wordlist", help="wordlist for web content discovery")
    _common_args(parser)


def recon(args) -> int:
    if not args.dry_run and not _authorized(args.target, args.yes):
        return 2
    return ReconWorkflow(
        args.target, wordlist=args.wordlist, dry_run=args.dry_run,
        base=_base(args), name=args.name,
    ).run()


# --- web ---------------------------------------------------------------------
def add_web_args(parser) -> None:
    parser.add_argument("target", help="URL or host")
    _common_args(parser)


def web(args) -> int:
    if not args.dry_run and not _authorized(args.target, args.yes):
        return 2
    return WebWorkflow(args.target, dry_run=args.dry_run, base=_base(args), name=args.name).run()


# --- ad ----------------------------------------------------------------------
def add_ad_args(parser) -> None:
    parser.add_argument("target", help="Active Directory domain")
    parser.add_argument("--user", help="username for credentialed collection")
    parser.add_argument("--password", help="password for credentialed collection")
    parser.add_argument("--dc-ip", dest="dc_ip", help="domain controller IP")
    _common_args(parser)


def ad(args) -> int:
    if not args.dry_run and not _authorized(args.target, args.yes):
        return 2
    extra = {"user": args.user, "password": args.password, "dc_ip": args.dc_ip}
    return ADWorkflow(
        args.target, dry_run=args.dry_run, base=_base(args), name=args.name, extra=extra,
    ).run()
