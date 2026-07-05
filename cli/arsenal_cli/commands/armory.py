"""``arsenal armory`` (also the default when no subcommand is given).

Prints the weapon registry — weapon name -> real tool -> category -> what it
does — reading the same ``/usr/local/share/arsenal/registry`` that drives the
profile.d launchers, so the two never drift.

With ``--json`` it emits the same inventory as machine-readable JSON (weapon,
tool, category, description, installed) for scripting and dashboards. An
optional query filters weapons by name/tool/category/description (e.g.
``arsenal armory web``).
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


def _match(query: str | None, *fields: str) -> bool:
    """True if no query, or the (case-insensitive) query is a substring of any field."""
    if not query:
        return True
    q = query.lower()
    return any(q in f.lower() for f in fields)


def _inventory(query: str | None = None):
    """Return the weapon registry as a list of dicts (machine-readable)."""
    rows = []
    for weapon, binary, category, desc in _iter_registry(config.REGISTRY.read_text()):
        if not _match(query, weapon, binary, category, desc):
            continue
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


def _run_json(query: str | None = None) -> int:
    if not config.REGISTRY.is_file():
        print(json.dumps({"weapons": [], "count": 0, "error": "registry not found"}, indent=2))
        return 1
    rows = _inventory(query)
    payload = {"weapons": rows, "count": len(rows)}
    if query:
        payload["query"] = query
    print(json.dumps(payload, indent=2))
    return 0


def run(args) -> int:
    query = getattr(args, "query", None)
    if getattr(args, "json", False):
        return _run_json(query)

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
        if not _match(query, weapon, binary, category, desc):
            continue
        installed = runner.which(binary) is not None
        dot = ui.style("●", ui.GREEN) if installed else ui.style("○", ui.DIM)
        print(
            f"  {dot} {ui.style(f'{weapon:<12}', ui.RED)} "
            f"{ui.style(f'{binary:<16}', ui.CYAN)} {category:<18}{desc}"
        )
        count += 1

    print()
    if query and count == 0:
        print("  " + ui.style(f"no weapons match {query!r}", ui.DIM))
        return 0
    tail = f"● installed   ○ not on this image   ({count} weapon{'s' if count != 1 else ''}"
    tail += f" matching {query!r})" if query else ")"
    print("  " + ui.style(tail, ui.DIM))
    print(
        "  "
        + ui.style("Call a weapon by name (e.g. ", ui.DIM)
        + ui.style("sniper", ui.RED)
        + ui.style(") or run ", ui.DIM)
        + ui.style("arsenal doctor", ui.RED)
        + ui.style(".", ui.DIM)
    )
    return 0
