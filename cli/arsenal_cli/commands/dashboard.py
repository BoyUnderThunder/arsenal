"""``arsenal dashboard`` — a lightweight Arsenal status dashboard.

Generates a dark-themed HTML page (reusing the report theme) with security
status, firewall/AppArmor, updates, installed weapons and recent engagements,
and opens it via ``xdg-open`` (XFCE). ``--tui`` renders the same in the
terminal. No long-running daemon.
"""
from __future__ import annotations

import datetime
import html
import json
import os
from pathlib import Path

from .. import config, runner, ui
from ..report.render import _CSS
from ..version import os_version
from . import doctor

NAME = "dashboard"
HELP = "open the Arsenal status dashboard (HTML/XFCE, or --tui)"

_CLS = {ui.Status.OK: "ok", ui.Status.WARN: "fail", ui.Status.FAIL: "fail", ui.Status.INFO: "skip"}
_SYM = {ui.Status.OK: "✓", ui.Status.WARN: "!", ui.Status.FAIL: "✗", ui.Status.INFO: "i"}


def add_arguments(parser) -> None:
    parser.add_argument("--tui", action="store_true", help="render in the terminal")
    parser.add_argument("--no-open", action="store_true", help="generate HTML but don't open it")
    parser.add_argument("-o", "--output", help="HTML output path")


def _weapons() -> tuple[int, int]:
    reg = config.REGISTRY
    installed = total = 0
    if reg.is_file():
        for raw in reg.read_text().splitlines():
            s = raw.strip()
            if not s or s.startswith("#") or "|" not in s:
                continue
            total += 1
            if runner.which(s.split("|")[1].strip()):
                installed += 1
    return installed, total


def _recent(limit: int = 8) -> list[dict]:
    base = config.ENGAGEMENTS_DIR
    try:
        dirs = [d for d in base.iterdir() if (d / "arsenal.json").is_file()]
    except OSError:
        return []
    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    out = []
    for d in dirs[:limit]:
        try:
            meta = json.loads((d / "arsenal.json").read_text())
        except (OSError, json.JSONDecodeError):
            continue
        out.append({
            "name": meta.get("name", d.name),
            "kind": meta.get("kind", ""),
            "created": meta.get("created", ""),
            "report": str(d / "report" / "report.html"),
        })
    return out


def _collect() -> dict:
    return {
        "version": os_version(),
        "checks": doctor.gather(),
        "weapons": _weapons(),
        "recent": _recent(),
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _render_html(data: dict) -> str:
    inst, total = data["weapons"]
    checks_html = "".join(
        f"<tr><td class='{_CLS[c.status]} badge'>{_SYM[c.status]}</td>"
        f"<td>{html.escape(c.name)}</td><td class='meta'>{html.escape(c.detail)}</td></tr>"
        for c in data["checks"]
    )
    if data["recent"]:
        recent_html = "".join(
            f"<tr><td>{html.escape(r['name'])}</td><td>{html.escape(r['kind'])}</td>"
            f"<td class='meta'>{html.escape(r['created'])}</td>"
            f"<td><a href='file://{html.escape(r['report'])}'>report</a></td></tr>"
            for r in data["recent"]
        )
        recent_block = ("<table><thead><tr><th>Engagement</th><th>Type</th>"
                        "<th>Created</th><th></th></tr></thead><tbody>"
                        f"{recent_html}</tbody></table>")
    else:
        recent_block = "<p class='meta'>No engagements yet — try <code>arsenal recon &lt;target&gt;</code>.</p>"

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="60">
<title>Arsenal Dashboard</title><style>{_CSS}
.cards{{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:8px;
padding:1rem 1.3rem;min-width:180px}} .card .big{{font-size:1.6rem;color:var(--cyan)}}
</style></head><body>
<h1>Arsenal Dashboard</h1>
<p class="meta">Version: {html.escape(data['version'])} &nbsp;·&nbsp; Generated: {data['generated']}</p>
<div class="cards">
  <div class="card"><div>Weapons</div><div class="big">{inst}/{total}</div><div class="meta">installed</div></div>
  <div class="card"><div>Security checks</div><div class="big">{sum(1 for c in data['checks'] if c.status==ui.Status.OK)}/{len(data['checks'])}</div><div class="meta">passing</div></div>
  <div class="card"><div>Engagements</div><div class="big">{len(data['recent'])}</div><div class="meta">recent</div></div>
</div>
<h2>Security status</h2>
<table><tbody>{checks_html}</tbody></table>
<h2>Recent engagements</h2>
{recent_block}
<p class="footer">Arsenal · auto-refreshes every 60s</p>
</body></html>
"""


def _render_tui(data: dict) -> int:
    print(ui.header("Arsenal Dashboard"))
    print("  " + ui.style(f"version {data['version']}", ui.DIM))
    inst, total = data["weapons"]
    print("  " + ui.style(f"weapons: {inst}/{total} installed", ui.DIM))
    print()
    for c in data["checks"]:
        ui.print_status(c.status, c.name, c.detail)
    print()
    print(ui.style("  Recent engagements:", ui.BOLD))
    if not data["recent"]:
        print("  " + ui.style("none yet", ui.DIM))
    for r in data["recent"]:
        print(f"  {ui.style(r['name'], ui.RED)}  {r['kind']}  {ui.style(r['created'], ui.DIM)}")
    return 0


def run(args) -> int:
    data = _collect()
    if args.tui:
        return _render_tui(data)

    if args.output:
        out = Path(args.output)
    else:
        cache = Path(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")))
        out = cache / "arsenal" / "dashboard.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_render_html(data))
    ui.print_status(ui.Status.OK, "dashboard generated", str(out))

    if not args.no_open and runner.which("xdg-open"):
        runner.run(["xdg-open", str(out)], timeout=10)
        ui.print_status(ui.Status.INFO, "opened in your browser")
    else:
        print("  " + ui.style(f"open: file://{out}", ui.DIM))
    return 0
