"""`recon` workflow: nmap service scan + web content discovery (ffuf/gobuster)."""
from __future__ import annotations

from .. import runner
from .base import Finding, Task, Workflow, as_host, as_url, find_wordlist, first_lines


def _open_ports(stdout: str) -> list[str]:
    return [ln.strip() for ln in stdout.splitlines() if "/tcp" in ln and "open" in ln]


def _nmap_summary(res: runner.Result) -> str:
    opens = _open_ports(res.stdout)
    return f"{len(opens)} open TCP port(s)" if opens else first_lines(res.stdout)


def _nmap_findings(host: str):
    """Turn nmap's open-port lines into informational findings (attack surface)."""
    def producer(res: runner.Result) -> list[Finding]:
        out: list[Finding] = []
        for line in _open_ports(res.stdout):
            port = line.split("/", 1)[0].strip()
            parts = line.split()
            svc = parts[2] if len(parts) >= 3 else ""
            title = f"Open TCP port {port}" + (f" ({svc})" if svc else "")
            out.append(Finding(title=title, severity="info", target=host, evidence=line))
        return out
    return producer


class ReconWorkflow(Workflow):
    kind = "recon"
    description = "Network + web reconnaissance"

    def plan(self) -> list[Task]:
        host, url = as_host(self.target), as_url(self.target)
        tasks = [
            Task("nmap", ["nmap", "-sV", "-Pn", "-T4", host], timeout=1200,
                 summarize=_nmap_summary, find=_nmap_findings(host)),
        ]
        wordlist = find_wordlist(self.wordlist)
        if wordlist:
            tasks.append(Task(
                "gobuster", ["gobuster", "dir", "-q", "-u", url, "-w", wordlist, "-t", "40"],
                timeout=900, optional=True,
            ))
            tasks.append(Task(
                "ffuf", ["ffuf", "-s", "-u", f"{url}/FUZZ", "-w", wordlist],
                timeout=900, optional=True,
            ))
        else:
            tasks.append(Task(
                "web-content-discovery",
                note="skipped: no wordlist found — install seclists or pass --wordlist",
            ))
        return tasks
