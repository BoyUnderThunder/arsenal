"""Workflow engine core: the :class:`Task`/:class:`Workflow` model that runs a
chain of tools, records results into a project, and writes a report."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .. import runner, ui
from ..log import get_logger
from ..project import Project, Step
from ..report import render_html, render_markdown

log = get_logger(__name__)

# Common locations for a web-content wordlist (seclists etc. are not bundled).
WORDLIST_CANDIDATES = [
    "/usr/share/seclists/Discovery/Web-Content/common.txt",
    "/usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt",
    "/usr/share/wordlists/dirb/common.txt",
    "/usr/share/wordlists/dirbuster/directory-list-2.3-small.txt",
]


def find_wordlist(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit if Path(explicit).is_file() else None
    for cand in WORDLIST_CANDIDATES:
        if Path(cand).is_file():
            return cand
    return None


def first_lines(text: str | None, n: int = 1) -> str:
    lines = [l for l in (text or "").splitlines() if l.strip()]
    return " ".join(lines[:n])[:200]


@dataclass
class Task:
    """One unit of work in a workflow.

    With ``argv`` it runs a command; without ``argv`` it is a manual/info note
    recorded in the report (e.g. "launch Burp Suite — no headless API").
    """

    name: str
    argv: list[str] = field(default_factory=list)
    timeout: float = 600.0
    optional: bool = False
    ext: str = "txt"
    summarize: Optional[Callable[[runner.Result], str]] = None
    note: str = ""


class Workflow:
    kind = "manual"
    description = ""

    def __init__(
        self,
        target: str,
        *,
        name: str | None = None,
        base: Path | None = None,
        dry_run: bool = False,
        wordlist: str | None = None,
        extra: dict | None = None,
    ):
        self.target = target
        self.name = name or f"{self.kind}-{target}"
        self.base = base
        self.dry_run = dry_run
        self.wordlist = wordlist
        self.extra = extra or {}

    # Subclasses implement this.
    def plan(self) -> list[Task]:
        raise NotImplementedError

    def run(self) -> int:
        tasks = self.plan()

        if self.dry_run:
            print(ui.header(f"Arsenal {self.kind} — plan for {self.target}"))
            for t in tasks:
                detail = " ".join(t.argv) if t.argv else (t.note or "(manual)")
                print("  " + ui.style(t.name, ui.RED) + ": " + ui.style(detail, ui.DIM))
            return 0

        proj = Project.create(self.name, kind=self.kind, target=self.target, base=self.base)
        print(ui.header(f"Arsenal {self.kind} — {self.target}"))
        print("  " + ui.style(f"project: {proj.path}", ui.DIM))

        for task in tasks:
            self._run_task(proj, task)

        report_dir = proj.path / "report"  # type: ignore[operator]
        (report_dir / "report.md").write_text(render_markdown(proj))
        (report_dir / "report.html").write_text(render_html(proj))

        counts = proj.counts()
        print()
        ui.print_status(
            ui.Status.OK if counts["fail"] == 0 else ui.Status.WARN,
            f"{self.kind} complete",
            f"{counts['ok']} ok · {counts['fail']} failed · {counts['skipped']} skipped",
        )
        print("  " + ui.style(f"report: {report_dir / 'report.html'}", ui.DIM))
        return 0 if counts["fail"] == 0 else 1

    def _run_task(self, proj: Project, task: Task) -> None:
        step = Step(
            name=task.name,
            command=" ".join(task.argv) if task.argv else task.note,
            started=datetime.datetime.now().strftime("%H:%M:%S"),
        )

        # Manual / informational step (no command to run).
        if not task.argv:
            step.status = "skipped"
            step.summary = task.note or "manual step"
            ui.print_status(ui.Status.INFO, task.name, step.summary)
            proj.add_step(step)
            return

        tool = task.argv[0]
        if runner.which(tool) is None:
            step.status = "skipped"
            step.summary = f"{tool} not installed"
            ui.print_status(ui.Status.WARN, task.name, step.summary)
            proj.add_step(step)
            return

        res = runner.run(task.argv, timeout=task.timeout)
        out_file = proj.scans_dir() / f"{task.name}.{task.ext}"
        body = res.stdout or ""
        if res.stderr.strip():
            body += "\n[stderr]\n" + res.stderr
        out_file.write_text(body)

        step.output_file = str(out_file)
        step.returncode = res.returncode
        step.finished = datetime.datetime.now().strftime("%H:%M:%S")
        if res.timed_out:
            step.status, step.summary = "fail", "timed out"
        elif res.ok:
            step.status = "ok"
        else:
            step.status = "fail"

        if task.summarize and not res.timed_out:
            try:
                step.summary = task.summarize(res) or step.summary
            except Exception:  # a summariser bug must not break the workflow
                log.exception("summariser for %s failed", task.name)
        if not step.summary:
            step.summary = first_lines(res.stdout) or f"exit {res.returncode}"

        status_ui = {
            "ok": ui.Status.OK,
            "fail": ui.Status.FAIL,
            "skipped": ui.Status.WARN,
        }[step.status]
        ui.print_status(status_ui, task.name, step.summary)
        proj.add_step(step)
