"""``arsenal armory`` (also the default when no subcommand is given).

Prints the weapon registry — weapon name -> real tool -> category -> what it
does — reading the same ``/usr/local/share/arsenal/registry`` that drives the
profile.d launchers, so the two never drift.

With ``--json`` it emits the same inventory as machine-readable JSON (weapon,
tool, category, description, installed) for scripting and dashboards. An
optional query filters weapons by name/tool/category/description (e.g.
``arsenal armory web``), and ``--installed`` / ``--missing`` filter by whether
the tool is present on this image.
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


def _inventory(query: str | None = None, presence: str | None = None):
    """Return the (filtered) weapon registry as a list of dicts.

    ``presence`` is ``"installed"``, ``"missing"``, or ``None`` (all). This is
    the single reader both the table and ``--json`` render from, so they can
    never disagree about the weapon set.
    """
    rows = []
    for weapon, binary, category, desc in _iter_registry(config.REGISTRY.read_text()):
        if not _match(query, weapon, binary, category, desc):
            continue
        installed = runner.which(binary) is not None
        if presence == "installed" and not installed:
            continue
        if presence == "missing" and installed:
            continue
        rows.append(
            {
                "weapon": weapon,
                "tool": binary,
                "category": category,
                "description": desc,
                "installed": installed,
            }
        )
    return rows


def _filter_desc(query: str | None, presence: str | None) -> str:
    """Human description of the active filters, for footers/empty messages."""
    parts = []
    if query:
        parts.append(f"matching {query!r}")
    if presence:
        parts.append(presence)
    return ", ".join(parts)


def _run_json(query: str | None, presence: str | None) -> int:
    if not config.REGISTRY.is_file():
        print(json.dumps({"weapons": [], "count": 0, "error": "registry not found"}, indent=2))
        return 1
    rows = _inventory(query, presence)
    payload = {"weapons": rows, "count": len(rows)}
    if query:
        payload["query"] = query
    if presence:
        payload["filter"] = presence
    print(json.dumps(payload, indent=2))
    return 0


def run(args) -> int:
    query = getattr(args, "query", None)
    presence = "installed" if getattr(args, "installed", False) else \
        "missing" if getattr(args, "missing", False) else None

    if getattr(args, "json", False):
        return _run_json(query, presence)

    print(ui.style(BANNER, ui.RED))
    print(ui.style("        white-hat security OS · the armory", ui.DIM))

    if not config.REGISTRY.is_file():
        ui.print_status(ui.Status.FAIL, f"registry not found at {config.REGISTRY}")
        return 1

    rows = _inventory(query, presence)

    print()
    print(
        "  "
        + ui.style(f"{'WEAPON':<14}{'TOOL':<16}{'CATEGORY':<18}WHAT IT DOES", ui.BOLD)
    )
    print("  " + ui.style("─" * 72, ui.DIM))

    for r in rows:
        dot = ui.style("●", ui.GREEN) if r["installed"] else ui.style("○", ui.DIM)
        weapon = ui.style(f"{r['weapon']:<12}", ui.RED)
        tool = ui.style(f"{r['tool']:<16}", ui.CYAN)
        print(f"  {dot} {weapon} {tool} {r['category']:<18}{r['description']}")

    desc = _filter_desc(query, presence)
    print()
    if desc and not rows:
        print("  " + ui.style(f"no weapons {desc}", ui.DIM))
        return 0
    n = len(rows)
    body = f"{n} weapon{'s' if n != 1 else ''}"
    if desc:
        body += f" {desc}"
    print("  " + ui.style(f"● installed   ○ not on this image   ({body})", ui.DIM))
    print(
        "  "
        + ui.style("Call a weapon by name (e.g. ", ui.DIM)
        + ui.style("sniper", ui.RED)
        + ui.style(") or run ", ui.DIM)
        + ui.style("arsenal doctor", ui.RED)
        + ui.style(".", ui.DIM)
    )
    return 0
