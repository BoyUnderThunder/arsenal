"""``arsenal engagements`` — list, inspect, re-run, archive, or delete the
engagement projects recorded under ``~/engagements`` (``ARSENAL_ENGAGEMENTS``).

Complements ``arsenal report`` (which renders one project) with lifecycle
management, so projects aren't just an opaque pile of timestamped directories.
"""
from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

from .. import config, ui
from ..project import SEVERITIES, Project

NAME = "engagements"
HELP = "list / show / rerun / archive / delete engagement projects"

# kind -> Workflow class, for `rerun`. Imported lazily to avoid a heavy import
# on the common `list`/`show` paths.
_ACTIONS = ("list", "show", "rerun", "delete", "archive")


def add_arguments(parser) -> None:
    parser.add_argument("action", nargs="?", default="list", choices=_ACTIONS,
                        help="what to do (default: list)")
    parser.add_argument("project", nargs="?",
                        help="engagement directory (for show/rerun/delete/archive)")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="skip confirmation (delete) / authorization prompt (rerun)")
    parser.add_argument("-o", "--output", help="archive output path (archive)")


def _iter_projects() -> list[Path]:
    base = config.ENGAGEMENTS_DIR
    try:
        dirs = [d for d in base.iterdir() if (d / "arsenal.json").is_file()]
    except OSError:
        return []
    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return dirs


def _load(project: str | None):
    if not project:
        ui.print_status(ui.Status.FAIL, "no project given", "usage: arsenal engagements <action> <dir>")
        return None
    path = Path(project)
    if not (path / "arsenal.json").is_file():
        ui.print_status(ui.Status.FAIL, f"no engagement at {path}", "expected an arsenal.json")
        return None
    return Project.load(path)


def _findings_line(p: Project) -> str:
    fc = p.finding_counts()
    brk = " · ".join(f"{fc[s]} {s}" for s in SEVERITIES if fc[s])
    return f"{len(p.findings)} finding(s)" + (f" — {brk}" if brk else "")


def _cmd_list() -> int:
    print(ui.header("Arsenal Engagements"))
    dirs = _iter_projects()
    if not dirs:
        print("  " + ui.style(f"none yet under {config.ENGAGEMENTS_DIR}", ui.DIM))
        print("  " + ui.style("start one:  arsenal recon <target>", ui.DIM))
        return 0
    for d in dirs:
        try:
            p = Project.load(d)
        except Exception:
            continue
        c = p.counts()
        print(f"  {ui.style(p.name, ui.RED)}  {ui.style(p.kind, ui.CYAN)}  {p.target or '—'}")
        print("    " + ui.style(
            f"{c['ok']} ok · {c['fail']} fail · {c['skipped']} skip · "
            f"{len(p.findings)} finding(s)  ·  {p.created}", ui.DIM))
        print("    " + ui.style(str(d), ui.DIM))
    print()
    print("  " + ui.style(f"{len(dirs)} engagement(s) in {config.ENGAGEMENTS_DIR}", ui.DIM))
    return 0


def _cmd_show(args) -> int:
    p = _load(args.project)
    if p is None:
        return 1
    print(ui.header(f"Engagement — {p.name}"))
    print("  " + ui.style(f"{p.kind} · {p.target or '—'} · {p.created}", ui.DIM))
    print("  " + ui.style(_findings_line(p), ui.DIM))
    print()
    for s in p.steps:
        status = {"ok": ui.Status.OK, "fail": ui.Status.FAIL}.get(s.status, ui.Status.WARN)
        ui.print_status(status, s.name, s.summary)
    if p.findings:
        print()
        print("  " + ui.style("Findings:", ui.BOLD))
        for f in p.findings_sorted():
            print(f"    [{f.severity}] {ui.style(f.title, ui.RED)}"
                  + (f"  ({f.target})" if f.target else ""))
    return 0


def _cmd_rerun(args) -> int:
    p = _load(args.project)
    if p is None:
        return 1
    from ..workflows.ad import ADWorkflow
    from ..workflows.recon import ReconWorkflow
    from ..workflows.web import WebWorkflow
    from .workflow import _authorized

    workflows = {"recon": ReconWorkflow, "web": WebWorkflow, "ad": ADWorkflow}
    wf_cls = workflows.get(p.kind)
    if wf_cls is None:
        ui.print_status(ui.Status.WARN, f"cannot rerun a '{p.kind}' engagement",
                        "only recon/web/ad are runnable")
        return 1
    if not p.target:
        ui.print_status(ui.Status.FAIL, "engagement has no target to rerun")
        return 1
    # Reruns launch active tooling — same authorization gate as a fresh run.
    # Credentials were redacted at record time, so an AD rerun covers only the
    # uncredentialed steps.
    if not _authorized(p.target, args.yes):
        return 2
    return wf_cls(p.target).run()


def _cmd_delete(args) -> int:
    p = _load(args.project)
    if p is None:
        return 1
    path = Path(args.project)
    if not args.yes:
        import sys
        if not sys.stdin.isatty():
            ui.print_status(ui.Status.FAIL, "refusing to delete without confirmation",
                            "pass --yes", file=sys.stderr)
            return 1
        try:
            if input(f"  Delete {path} ? [y/N] ").strip().lower() not in ("y", "yes"):
                print("  aborted")
                return 0
        except EOFError:
            return 1
    shutil.rmtree(path)
    ui.print_status(ui.Status.OK, "deleted", str(path))
    return 0


def _cmd_archive(args) -> int:
    p = _load(args.project)
    if p is None:
        return 1
    path = Path(args.project)
    out = Path(args.output) if args.output else path.with_suffix(".tar.gz")
    with tarfile.open(out, "w:gz") as tar:
        tar.add(path, arcname=path.name)
    ui.print_status(ui.Status.OK, "archived", str(out))
    return 0


def run(args) -> int:
    action = getattr(args, "action", "list") or "list"
    if action == "list":
        return _cmd_list()
    return {"show": _cmd_show, "rerun": _cmd_rerun,
            "delete": _cmd_delete, "archive": _cmd_archive}[action](args)
