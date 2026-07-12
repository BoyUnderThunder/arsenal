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

# Severity levels, most- to least-severe (also the report display order).
SEVERITIES = ("critical", "high", "medium", "low", "info")
_SEV_RANK = {s: i for i, s in enumerate(SEVERITIES)}


def severity_rank(sev: str) -> int:
    """Sort key for a severity string; unknown severities sort last."""
    return _SEV_RANK.get(str(sev).lower(), len(SEVERITIES))


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
class Finding:
    """A security finding surfaced by a workflow tool — the unit that turns a
    report from a step-list into an assessment."""

    title: str
    severity: str = "info"  # critical | high | medium | low | info
    target: str = ""
    evidence: str = ""
    refs: list[str] = field(default_factory=list)


@dataclass
class Project:
    name: str
    kind: str = "manual"  # recon | web | ad | manual
    target: str = ""
    created: str = ""
    arsenal_version: str = ""
    summary: str = ""  # free text / AI-generated summary (Phase 7)
    steps: list[Step] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
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
        findings = [Finding(**f) for f in data.pop("findings", [])]
        data.pop("path", None)
        return cls(steps=steps, findings=findings, path=path, **data)

    # --- mutation ------------------------------------------------------------
    def add_step(self, step: Step) -> Step:
        self.steps.append(step)
        self.save()
        return step

    def add_finding(self, finding: Finding) -> Finding:
        self.findings.append(finding)
        self.save()
        return finding

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

    def finding_counts(self) -> dict[str, int]:
        """Findings tallied by severity (every level present, 0 by default)."""
        out = dict.fromkeys(SEVERITIES, 0)
        for f in self.findings:
            key = str(f.severity).lower()
            out[key] = out.get(key, 0) + 1
        return out

    def findings_sorted(self) -> list[Finding]:
        """Findings ordered most-severe first (stable within a severity)."""
        return sorted(self.findings, key=lambda f: severity_rank(f.severity))
