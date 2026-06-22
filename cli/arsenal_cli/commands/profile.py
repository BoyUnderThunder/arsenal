"""``arsenal profile`` — install curated toolsets (red/blue/forensics/reverse).

Package lists live in ``arsenal_cli/data/profiles/*.list`` and are installed via
pacman at runtime (names resolve against the live repos, BlackArch included).
"""
from __future__ import annotations

import os
from pathlib import Path

from .. import runner, ui
from ..log import get_logger

log = get_logger(__name__)

NAME = "profile"
HELP = "install a curated toolset (red|blue|forensics|reverse)"

PROFILES_DIR = Path(__file__).resolve().parent.parent / "data" / "profiles"

DESCRIPTIONS = {
    "red": "Offensive — recon, web, AD, exploitation extras",
    "blue": "Defensive — IDS/NSM, monitoring, host hardening & AV",
    "forensics": "DFIR — disk/memory forensics, carving & recovery",
    "reverse": "Reverse engineering — disassemblers, debuggers, RE tooling",
}


def add_arguments(parser) -> None:
    parser.add_argument("name", nargs="?", help="profile to install, or 'list'")
    parser.add_argument("--show", action="store_true", help="show packages without installing")
    parser.add_argument("-y", "--yes", action="store_true", help="install without confirmation")


def available() -> list[str]:
    return sorted(p.stem for p in PROFILES_DIR.glob("*.list"))


def packages(name: str) -> list[str]:
    path = PROFILES_DIR / f"{name}.list"
    pkgs: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            pkgs.append(line)
    return pkgs


def _print_list() -> int:
    print(ui.header("Arsenal Profiles"))
    for name in available():
        print(f"  {ui.style(name, ui.RED)}  {ui.style(DESCRIPTIONS.get(name, ''), ui.DIM)}")
    print("\n  " + ui.style("Install with: arsenal profile <name>", ui.DIM))
    return 0


def run(args) -> int:
    name = args.name
    if not name or name == "list":
        return _print_list()

    if name not in available():
        ui.print_status(ui.Status.FAIL, f"unknown profile '{name}'",
                        "available: " + ", ".join(available()))
        return 1

    pkgs = packages(name)
    print(ui.header(f"Arsenal Profile — {name}"))
    print("  " + ui.style(DESCRIPTIONS.get(name, ""), ui.DIM))
    print("  " + ui.style(f"{len(pkgs)} packages: ", ui.DIM) + ", ".join(pkgs))

    if args.show:
        return 0

    if os.geteuid() != 0:
        ui.print_status(ui.Status.FAIL, "root required", "re-run with sudo to install packages")
        return 1

    if not args.yes:
        try:
            if input("\n  Install these packages? [y/N] ").strip().lower() not in ("y", "yes"):
                ui.print_status(ui.Status.INFO, "aborted")
                return 0
        except EOFError:
            ui.print_status(ui.Status.FAIL, "no confirmation (use --yes)")
            return 1

    log.info("installing profile %s: %s", name, " ".join(pkgs))
    runner.run(["pacman", "-Sy", "--noconfirm"], timeout=300)  # refresh DBs
    res = runner.run(["pacman", "-S", "--needed", "--noconfirm", *pkgs], timeout=3600)
    if res.ok:
        ui.print_status(ui.Status.OK, f"profile '{name}' installed")
        return 0
    ui.print_status(ui.Status.FAIL, f"profile '{name}' install had errors",
                    "some package names may differ in the live repos")
    print(ui.style((res.stderr or res.stdout).strip()[-400:], ui.DIM))
    return 1
