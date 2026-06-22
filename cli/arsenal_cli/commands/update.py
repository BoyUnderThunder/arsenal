"""``arsenal update`` — safe system maintenance.

Refreshes repos, upgrades packages (keyrings first to avoid partial-upgrade
breakage), prepares rollback material, verifies Arsenal components afterwards,
and records an update history. ``--check`` only reports pending updates.
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path

from .. import runner, ui
from ..log import get_logger

log = get_logger(__name__)

NAME = "update"
HELP = "refresh repos, upgrade packages, verify Arsenal (with rollback prep)"


def add_arguments(parser) -> None:
    parser.add_argument("--check", action="store_true", help="only show pending updates")
    parser.add_argument("-y", "--yes", action="store_true", help="upgrade without confirmation")
    parser.add_argument("--no-snapshot", action="store_true",
                        help="skip the Timeshift snapshot hook")


def _updates_dir() -> Path:
    base = Path(os.environ.get("ARSENAL_LOG_DIR", "/var/log/arsenal"))
    return base / "updates"


def _pending() -> list[str]:
    if runner.which("checkupdates"):
        res = runner.run(["checkupdates"], timeout=120)
    else:
        res = runner.run(["pacman", "-Qu"], timeout=120)
    return [l for l in res.stdout.splitlines() if l.strip()]


def _prepare_rollback(no_snapshot: bool) -> Path:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    snap = _updates_dir() / ts
    try:
        snap.mkdir(parents=True, exist_ok=True)
        explicit = runner.run(["pacman", "-Qqe"], timeout=60)
        (snap / "explicit-packages.txt").write_text(explicit.stdout)
        allpkgs = runner.run(["pacman", "-Q"], timeout=60)
        (snap / "all-packages.txt").write_text(allpkgs.stdout)
        (snap / "ROLLBACK.txt").write_text(
            "Pre-update package state.\n\n"
            "To roll a package back, reinstall the cached version:\n"
            "  pacman -U /var/cache/pacman/pkg/<name>-<oldver>.pkg.tar.zst\n"
            "Full lists: all-packages.txt (with versions), explicit-packages.txt.\n"
        )
        ui.print_status(ui.Status.OK, "rollback state saved", str(snap))
    except OSError as exc:
        ui.print_status(ui.Status.WARN, "could not save rollback state", str(exc))

    if not no_snapshot and runner.which("timeshift"):
        res = runner.run(["timeshift", "--create", "--comments", "pre-arsenal-update"],
                         timeout=900)
        ui.print_status(
            ui.Status.OK if res.ok else ui.Status.WARN,
            "Timeshift snapshot" + ("" if res.ok else " skipped"),
        )
    return snap


def _verify() -> None:
    print(ui.header("Post-update verification"))
    registry = Path("/usr/local/share/arsenal/registry")
    ui.print_status(
        ui.Status.OK if registry.is_file() else ui.Status.WARN,
        "armory registry present" if registry.is_file() else "armory registry missing",
    )
    hardened = "hardened" in os.uname().release
    ui.print_status(ui.Status.OK if hardened else ui.Status.WARN,
                    "hardened kernel" if hardened else "kernel is not linux-hardened (reboot?)",
                    os.uname().release)
    for svc in ("apparmor", "nftables"):
        active = runner.run(["systemctl", "is-active", svc], timeout=10).stdout.strip() == "active"
        ui.print_status(ui.Status.OK if active else ui.Status.WARN, f"service {svc}",
                        "active" if active else "inactive")


def _log_history(result: str, pending: int) -> None:
    try:
        hist = _updates_dir() / "history.log"
        hist.parent.mkdir(parents=True, exist_ok=True)
        with hist.open("a") as fh:
            fh.write(f"{datetime.datetime.now():%Y-%m-%dT%H:%M:%S} result={result} pending_before={pending}\n")
    except OSError:
        pass


def run(args) -> int:
    pending = _pending()

    if args.check:
        print(ui.header("Pending updates"))
        if pending:
            for line in pending:
                print("  " + line)
            ui.print_status(ui.Status.WARN, f"{len(pending)} update(s) available")
        else:
            ui.print_status(ui.Status.OK, "system is up to date")
        return 0

    if os.geteuid() != 0:
        ui.print_status(ui.Status.FAIL, "root required", "re-run with sudo")
        return 1

    print(ui.header("Arsenal Update"))
    ui.print_status(ui.Status.INFO, f"{len(pending)} package(s) pending" if pending else "no pending updates")

    if not args.yes:
        try:
            if input("  Proceed with full upgrade? [y/N] ").strip().lower() not in ("y", "yes"):
                ui.print_status(ui.Status.INFO, "aborted")
                return 0
        except EOFError:
            ui.print_status(ui.Status.FAIL, "no confirmation (use --yes)")
            return 1

    _prepare_rollback(args.no_snapshot)

    # Keyrings first — avoids signature failures during the main upgrade.
    log.info("update: refreshing keyrings")
    runner.run(["pacman", "-Sy", "--noconfirm", "archlinux-keyring"], timeout=600)
    if runner.which("pacman"):
        runner.run(["pacman", "-S", "--noconfirm", "--needed", "blackarch-keyring"], timeout=600)

    log.info("update: full system upgrade")
    res = runner.run(["pacman", "-Syu", "--noconfirm"], timeout=7200)

    if res.ok:
        ui.print_status(ui.Status.OK, "system upgraded")
        _verify()
        _log_history("ok", len(pending))
        return 0

    ui.print_status(ui.Status.FAIL, "upgrade failed",
                    "see rollback material in " + str(_updates_dir()))
    print(ui.style((res.stderr or res.stdout).strip()[-500:], ui.DIM))
    _log_history("fail", len(pending))
    return 1
