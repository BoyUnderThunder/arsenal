"""`recon` workflow: nmap service scan + web content discovery (ffuf/gobuster)."""
from __future__ import annotations

from .. import runner
from .base import Task, Workflow, find_wordlist, first_lines


def _host(target: str) -> str:
    return target.replace("https://", "").replace("http://", "").split("/")[0]


def _url(target: str) -> str:
    return target if target.startswith(("http://", "https://")) else f"http://{target}"


def _nmap_summary(res: runner.Result) -> str:
    opens = [l for l in res.stdout.splitlines() if "/tcp" in l and "open" in l]
    return f"{len(opens)} open TCP port(s)" if opens else first_lines(res.stdout)


class ReconWorkflow(Workflow):
    kind = "recon"
    description = "Network + web reconnaissance"

    def plan(self) -> list[Task]:
        host, url = _host(self.target), _url(self.target)
        tasks = [
            Task("nmap", ["nmap", "-sV", "-Pn", "-T4", host], timeout=1200,
                 summarize=_nmap_summary),
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
