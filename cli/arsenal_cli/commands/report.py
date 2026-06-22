"""``arsenal report <project>`` — render an engagement project to Markdown /
HTML / PDF."""
from __future__ import annotations

from pathlib import Path

from .. import ui
from ..project import Project
from ..report import render_html, render_markdown, render_pdf

NAME = "report"
HELP = "generate a report (md/html/pdf) from an engagement project"


def add_arguments(parser) -> None:
    parser.add_argument("project", help="path to an Arsenal engagement project directory")
    parser.add_argument(
        "-f", "--format", choices=["md", "html", "pdf", "all"], default="all",
        help="output format (default: all)",
    )
    parser.add_argument("-o", "--output", help="output directory (default: <project>/report)")


def run(args) -> int:
    proj_path = Path(args.project)
    if not (proj_path / "arsenal.json").is_file():
        ui.print_status(ui.Status.FAIL, f"no Arsenal project at {proj_path}",
                        "expected an arsenal.json")
        return 1

    proj = Project.load(proj_path)
    formats = ["md", "html", "pdf"] if args.format == "all" else [args.format]
    outdir = Path(args.output) if args.output else (proj.path or proj_path) / "report"
    outdir.mkdir(parents=True, exist_ok=True)

    print(ui.header(f"Arsenal Report — {proj.name}"))
    rc = 0

    if "md" in formats:
        f = outdir / "report.md"
        f.write_text(render_markdown(proj))
        ui.print_status(ui.Status.OK, "Markdown", str(f))

    if "html" in formats:
        f = outdir / "report.html"
        f.write_text(render_html(proj))
        ui.print_status(ui.Status.OK, "HTML", str(f))

    if "pdf" in formats:
        f = outdir / "report.pdf"
        ok, msg = render_pdf(proj, f)
        ui.print_status(ui.Status.OK if ok else ui.Status.WARN, "PDF", msg)
        if not ok and args.format == "pdf":
            rc = 1  # explicit pdf request that couldn't be fulfilled

    return rc
