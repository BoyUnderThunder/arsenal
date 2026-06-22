"""``arsenal reportbug`` — collect a redacted support bundle.

Gathers logs, kernel ring buffer, hardware info, package list and Arsenal
version into a single compressed archive, redacting obvious sensitive data
(IPs, MACs, secrets) unless ``--no-redact`` is given.
"""
from __future__ import annotations

import datetime
import re
import tempfile
from pathlib import Path

from .. import runner, ui
from ..version import os_version

# Output filename -> command run to populate it. A missing tool is recorded as
# such in its own file rather than failing the whole report.
_COMMANDS: dict[str, list[str]] = {
    "kernel.txt": ["uname", "-a"],
    "journalctl.txt": ["journalctl", "-b", "--no-pager"],
    "dmesg.txt": ["dmesg"],
    "hardware-lscpu.txt": ["lscpu"],
    "hardware-lspci.txt": ["lspci"],
    "hardware-inxi.txt": ["inxi", "-Fxz"],
    "packages.txt": ["pacman", "-Q"],
    "services-running.txt": ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager"],
    "services-failed.txt": ["systemctl", "--failed", "--no-pager"],
}

_REDACTIONS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IPV4]"),
    (re.compile(r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b"), "[MAC]"),
    (re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){4,7}[0-9a-fA-F]{1,4}\b"), "[IPV6]"),
    (re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key|bearer)\b\s*[=:]\s*\S+"),
     r"\1=[REDACTED]"),
]


def redact(text: str) -> str:
    for pattern, repl in _REDACTIONS:
        text = pattern.sub(repl, text)
    return text


def _collect() -> dict[str, str]:
    items: dict[str, str] = {"arsenal-version.txt": os_version() + "\n"}
    for filename, cmd in _COMMANDS.items():
        res = runner.run(cmd, timeout=60)
        if res.missing:
            items[filename] = f"[{cmd[0]} not installed]\n"
            continue
        body = res.stdout or ""
        if res.stderr.strip():
            body += "\n[stderr]\n" + res.stderr
        items[filename] = body
    return items


def run(args) -> int:
    do_redact = not getattr(args, "no_redact", False)
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    print(ui.header("Arsenal Bug Report"))

    items = _collect()
    with tempfile.TemporaryDirectory() as tmp:
        bundle_dir = Path(tmp) / f"arsenal-report-{timestamp}"
        bundle_dir.mkdir()
        for filename, content in items.items():
            if do_redact:
                content = redact(content)
            (bundle_dir / filename).write_text(content)

        default_out = f"/tmp/arsenal-report-{timestamp}.tar.zst"
        out = Path(getattr(args, "output", None) or default_out)
        if runner.which("zstd"):
            res = runner.run(
                ["tar", "--zstd", "-cf", str(out), "-C", str(bundle_dir.parent), bundle_dir.name],
                timeout=180,
            )
        else:
            out = Path(str(out).removesuffix(".tar.zst") + ".tar.gz")
            res = runner.run(
                ["tar", "-czf", str(out), "-C", str(bundle_dir.parent), bundle_dir.name],
                timeout=180,
            )

        if not res.ok:
            ui.print_status(ui.Status.FAIL, "failed to create support bundle", res.stderr.strip())
            return 1

    ui.print_status(ui.Status.OK, "support bundle created", str(out))
    ui.print_status(
        ui.Status.OK if do_redact else ui.Status.WARN,
        f"sensitive-data redaction {'on' if do_redact else 'OFF'}",
    )
    print("  " + ui.style("Review the bundle before sharing it.", ui.DIM))
    return 0
