"""Engagement *project* model — a structured directory that holds the results
of an Arsenal workflow (scans, loot, logs, report) plus machine-readable
metadata in ``arsenal.json``.

Both the workflow engine (which writes projects) and the report command (which
reads them) share this module so the on-disk format has a single definition.
"""
from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import ENGAGEMENTS_DIR
from .version import os_version

ISO_FMT = "%Y-%m-%dT%H:%M:%S"
SUBDIRS = ("scans", "loot", "logs", "report")


def _now() -> str:
    return datetime.datetime.now().strftime(ISO_FMT)


def _slug(name: str) -> str:
    cleaned = "".join(c if (c.isalnum() or c in "-_.") else "-" for c in name).strip("-")
    return cleaned or "project"


@dataclass
class Step:
    """A single tool invocation within a workflow."""

    name: str
    command: str = ""
    status: str = "pending"  # ok | fail | skipped | pending
    returncode: int | None = None
    started: str = ""
    finished: str = ""
    summary: str = ""
    output_file: str = ""


@dataclass
class Project:
    name: str
    kind: str = "manual"  # recon | web | ad | manual
    target: str = ""
    created: str = ""
    arsenal_version: str = ""
    summary: str = ""  # free text / AI-generated summary (Phase 7)
    steps: list[Step] = field(default_factory=list)
    path: Path | None = None  # runtime-only, not serialized

    # --- lifecycle -----------------------------------------------------------
    @classmethod
    def create(cls, name: str, kind: str = "manual", target: str = "",
               base: Path | None = None) -> Project:
        root = Path(base) if base else ENGAGEMENTS_DIR
        path = root / f"{_slug(name)}-{datetime.datetime.now():%Y%m%d-%H%M%S}"
        for sub in SUBDIRS:
            (path / sub).mkdir(parents=True, exist_ok=True)
        proj = cls(
            name=name,
            kind=kind,
            target=target,
            created=_now(),
            arsenal_version=os_version(),
            path=path,
        )
        proj.save()
        return proj

    @classmethod
    def load(cls, path) -> Project:
        path = Path(path)
        data = json.loads((path / "arsenal.json").read_text())
        steps = [Step(**s) for s in data.pop("steps", [])]
        data.pop("path", None)
        return cls(steps=steps, path=path, **data)

    # --- mutation ------------------------------------------------------------
    def add_step(self, step: Step) -> Step:
        self.steps.append(step)
        self.save()
        return step

    def save(self) -> None:
        if not self.path:
            return
        data = asdict(self)
        data.pop("path", None)
        (self.path / "arsenal.json").write_text(json.dumps(data, indent=2))

    # --- helpers -------------------------------------------------------------
    def scans_dir(self) -> Path:
        assert self.path is not None
        return self.path / "scans"

    def counts(self) -> dict[str, int]:
        out = {"ok": 0, "fail": 0, "skipped": 0, "pending": 0}
        for s in self.steps:
            out[s.status] = out.get(s.status, 0) + 1
        return out
