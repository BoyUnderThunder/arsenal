"""Render an engagement :class:`~arsenal_cli.project.Project` to Markdown, HTML
(dark themed, dependency-free) or PDF (via WeasyPrint when available)."""
from __future__ import annotations

import datetime
import html
from pathlib import Path

from ..project import SEVERITIES, Project

_STATUS_EMOJI = {"ok": "✓", "fail": "✗", "skipped": "–", "pending": "…"}


def _snippet(output_file: str, max_lines: int = 40, max_chars: int = 4000) -> str:
    """Read a step's saved scan output, truncated, for inline embedding. Empty
    string if the file is missing/unreadable."""
    if not output_file:
        return ""
    try:
        text = Path(output_file).read_text(errors="replace")
    except OSError:
        return ""
    lines = text.splitlines()
    body = "\n".join(lines[:max_lines])[:max_chars].rstrip()
    if len(lines) > max_lines or len(text) > max_chars:
        body += "\n… (truncated — see the full file on disk)"
    return body


def _sev_line(p: Project) -> str:
    """e.g. '3 findings — 1 high · 2 info' (non-zero severities, most-severe first)."""
    fc = p.finding_counts()
    parts = [f"{fc[s]} {s}" for s in SEVERITIES if fc[s]]
    return f"{len(p.findings)} finding(s)" + (" — " + " · ".join(parts) if parts else "")


def _cell(text) -> str:
    """Flatten a value so it cannot break a Markdown table row."""
    return str(text).replace("|", "/").replace("\n", " ").replace("\r", " ")


# --- Markdown ---------------------------------------------------------------
def render_markdown(p: Project) -> str:
    lines: list[str] = []
    a = lines.append
    a(f"# Arsenal Report — {p.name}")
    a("")
    a(f"- **Target:** {p.target or '—'}")
    a(f"- **Type:** {p.kind}")
    a(f"- **Created:** {p.created}")
    a(f"- **Arsenal:** {p.arsenal_version}")
    a(f"- **Generated:** {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    a("")
    if p.summary:
        a("## Summary")
        a("")
        a(p.summary)
        a("")
    if p.findings:
        a("## Findings")
        a("")
        a(_sev_line(p))
        a("")
        a("| Severity | Title | Target | Evidence | Refs |")
        a("|----------|-------|--------|----------|------|")
        for f in p.findings_sorted():
            a(f"| {_cell(f.severity)} | {_cell(f.title)} | {_cell(f.target)} "
              f"| {_cell(f.evidence)} | {_cell(', '.join(f.refs))} |")
        a("")
    c = p.counts()
    a("## Steps")
    a("")
    a(f"{c['ok']} ok · {c['fail']} failed · {c['skipped']} skipped")
    a("")
    a("| Step | Status | rc | Summary |")
    a("|------|--------|----|---------|")
    for s in p.steps:
        emoji = _STATUS_EMOJI.get(s.status, s.status)
        rc = "" if s.returncode is None else str(s.returncode)
        a(f"| {_cell(s.name)} | {emoji} {s.status} | {rc} | {_cell(s.summary)} |")
    a("")
    for s in p.steps:
        a(f"### {s.name}")
        a("")
        if s.command:
            a("```")
            a(s.command)
            a("```")
        if s.summary:
            a(s.summary)
        if s.output_file:
            snippet = _snippet(s.output_file)
            if snippet:
                a("")
                a("```")
                a(snippet)
                a("```")
            a(f"\n_Output:_ `{s.output_file}`")
        a("")
    return "\n".join(lines) + "\n"


# --- HTML (dark theme, no external deps) ------------------------------------
_CSS = """
:root{--bg:#16181d;--fg:#e6e6e6;--muted:#9aa0a6;--red:#ff5555;--cyan:#56b6c2;
--green:#4caf50;--card:#1d2027;--border:#2c313a;}
*{box-sizing:border-box}body{background:var(--bg);color:var(--fg);
font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;margin:0;padding:2rem;line-height:1.5}
h1{color:var(--red);border-bottom:2px solid var(--border);padding-bottom:.4rem}
h2{color:var(--cyan);margin-top:2rem}h3{color:var(--fg);margin-top:1.4rem}
.meta{color:var(--muted)}a{color:var(--cyan)}
table{border-collapse:collapse;width:100%;margin:1rem 0}
th,td{border:1px solid var(--border);padding:.5rem .7rem;text-align:left}
th{background:var(--card);color:var(--cyan)}
code,pre{background:#0f1115;border:1px solid var(--border);border-radius:4px}
pre{padding:.8rem;overflow:auto}code{padding:.1rem .3rem}
.ok{color:var(--green)}.fail{color:var(--red)}.skip{color:var(--muted)}
.badge{font-weight:bold}.footer{margin-top:3rem;color:var(--muted);font-size:.85rem}
.sev-critical{color:#ff4d4f;font-weight:bold}.sev-high{color:#ff7043;font-weight:bold}
.sev-medium{color:#ffb300}.sev-low{color:var(--cyan)}.sev-info{color:var(--muted)}
"""


def _h(text: str) -> str:
    return html.escape(str(text), quote=True)


def render_html(p: Project) -> str:
    cls = {"ok": "ok", "fail": "fail", "skipped": "skip", "pending": "skip"}
    rows = []
    for s in p.steps:
        rc = "" if s.returncode is None else _h(s.returncode)
        rows.append(
            f"<tr><td>{_h(s.name)}</td>"
            f"<td class='{cls.get(s.status,'')} badge'>{_h(s.status)}</td>"
            f"<td>{rc}</td><td>{_h(s.summary)}</td></tr>"
        )
    detail = []
    for s in p.steps:
        detail.append(f"<h3>{_h(s.name)}</h3>")
        if s.command:
            detail.append(f"<pre>{_h(s.command)}</pre>")
        if s.summary:
            detail.append(f"<p>{_h(s.summary)}</p>")
        if s.output_file:
            snippet = _snippet(s.output_file)
            if snippet:
                detail.append(
                    f"<details><summary>output ({_h(s.name)})</summary>"
                    f"<pre>{_h(snippet)}</pre></details>"
                )
            detail.append(f"<p class='meta'>Output: <code>{_h(s.output_file)}</code></p>")
    c = p.counts()
    summary_block = f"<h2>Summary</h2><p>{_h(p.summary)}</p>" if p.summary else ""

    findings_block = ""
    if p.findings:
        frows = []
        for f in p.findings_sorted():
            sev_cls = f"sev-{str(f.severity).lower()}"
            refs = _h(", ".join(f.refs))
            frows.append(
                f"<tr><td class='{sev_cls} badge'>{_h(f.severity)}</td>"
                f"<td>{_h(f.title)}</td><td>{_h(f.target)}</td>"
                f"<td>{_h(f.evidence)}</td><td>{refs}</td></tr>"
            )
        findings_block = (
            "<h2>Findings</h2>"
            f"<p class='meta'>{_h(_sev_line(p))}</p>"
            "<table><thead><tr><th>Severity</th><th>Title</th><th>Target</th>"
            "<th>Evidence</th><th>Refs</th></tr></thead>"
            f"<tbody>{''.join(frows)}</tbody></table>"
        )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Arsenal Report — {_h(p.name)}</title><style>{_CSS}</style></head>
<body>
<h1>Arsenal Report — {_h(p.name)}</h1>
<p class="meta">Target: {_h(p.target or '—')} &nbsp;·&nbsp; Type: {_h(p.kind)}
&nbsp;·&nbsp; Created: {_h(p.created)} &nbsp;·&nbsp; Arsenal: {_h(p.arsenal_version)}</p>
{summary_block}
{findings_block}
<h2>Steps</h2>
<p class="meta">{c['ok']} ok · {c['fail']} failed · {c['skipped']} skipped</p>
<table><thead><tr><th>Step</th><th>Status</th><th>rc</th><th>Summary</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
{''.join(detail)}
<p class="footer">Generated by Arsenal · {datetime.datetime.now():%Y-%m-%d %H:%M:%S}</p>
</body></html>
"""


# --- PDF (optional, via WeasyPrint) -----------------------------------------
def render_pdf(p: Project, out_path) -> tuple[bool, str]:
    """Render to PDF at ``out_path``. Returns (ok, message). PDF support is
    optional: if WeasyPrint is not installed we say so rather than failing."""
    try:
        from weasyprint import HTML  # type: ignore
    except Exception:
        return (
            False,
            "PDF export needs WeasyPrint — install it with: pacman -S python-weasyprint",
        )
    try:
        HTML(string=render_html(p)).write_pdf(str(out_path))
        return True, str(out_path)
    except Exception as exc:  # pragma: no cover - depends on optional dep
        return False, f"PDF render failed: {exc}"
