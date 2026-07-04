"""``arsenal armory`` (also the default when no subcommand is given).

Prints the weapon registry — weapon name -> real tool -> category -> what it
does — reading the same ``/usr/local/share/arsenal/registry`` that drives the
profile.d launchers, so the two never drift.

With ``--json`` it emits the same inventory as machine-readable JSON (weapon,
tool, category, description, installed) for scripting and dashboards.
"""
from __future__ import annotations

import json

from .. import config, runner, ui

BANNER = r"""
   █████╗ ██████╗ ███████╗███████╗███╗   ██╗ █████╗ ██╗
  ██╔══██╗██╔══██╗██╔════╝██╔════╝████╗  ██║██╔══██╗██║
  ███████║██████╔╝███████╗█████╗  ██╔██╗ ██║███████║██║
  ██╔══██║██╔══██╗╚════██║██╔══╝  ██║╚██╗██║██╔══██║██║
  ██║  ██║██║  ██║███████║███████╗██║ ╚████║██║  ██║███████╗
  ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝"""


def _iter_registry(text: str):
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4:
            yield parts[0], parts[1], parts[2], parts[3]


def _inventory():
    """Return the weapon registry as a list of dicts (machine-readable)."""
    rows = []
    for weapon, binary, category, desc in _iter_registry(config.REGISTRY.read_text()):
        rows.append(
            {
                "weapon": weapon,
                "tool": binary,
                "category": category,
                "description": desc,
                "installed": runner.which(binary) is not None,
            }
        )
    return rows


def _run_json() -> int:
    if not config.REGISTRY.is_file():
        print(json.dumps({"weapons": [], "count": 0, "error": "registry not found"}, indent=2))
        return 1
    rows = _inventory()
    print(json.dumps({"weapons": rows, "count": len(rows)}, indent=2))
    return 0


def run(args) -> int:
    if getattr(args, "json", False):
        return _run_json()

    print(ui.style(BANNER, ui.RED))
    print(ui.style("        white-hat security OS · the armory", ui.DIM))

    if not config.REGISTRY.is_file():
        ui.print_status(ui.Status.FAIL, f"registry not found at {config.REGISTRY}")
        return 1

    print()
    print(
        "  "
        + ui.style(f"{'WEAPON':<14}{'TOOL':<16}{'CATEGORY':<18}WHAT IT DOES", ui.BOLD)
    )
    print("  " + ui.style("─" * 72, ui.DIM))

    count = 0
    for weapon, binary, category, desc in _iter_registry(config.REGISTRY.read_text()):
        installed = runner.which(binary) is not None
        dot = ui.style("●", ui.GREEN) if installed else ui.style("○", ui.DIM)
        print(
            f"  {dot} {ui.style(f'{weapon:<12}', ui.RED)} "
            f"{ui.style(f'{binary:<16}', ui.CYAN)} {category:<18}{desc}"
        )
        count += 1

    print()
    print("  " + ui.style(f"● installed   ○ not on this image   ({count} weapons)", ui.DIM))
    print(
        "  "
        + ui.style("Call a weapon by name (e.g. ", ui.DIM)
        + ui.style("sniper", ui.RED)
        + ui.style(") or run ", ui.DIM)
        + ui.style("arsenal doctor", ui.RED)
        + ui.style(".", ui.DIM)
    )
    return 0
