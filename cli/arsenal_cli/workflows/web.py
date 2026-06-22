"""`web` workflow: nikto + sqlmap (automated) and a Burp Suite hand-off note.

Burp Suite Community has no headless/REST API, so it cannot be scripted; the
workflow records a manual step pointing at the ``tower`` launcher instead.
"""
from __future__ import annotations

from .base import Task, Workflow, as_url


class WebWorkflow(Workflow):
    kind = "web"
    description = "Web application assessment"

    def plan(self) -> list[Task]:
        url = as_url(self.target)
        return [
            Task("nikto", ["nikto", "-host", url, "-ask", "no"], timeout=1200, optional=True),
            Task("sqlmap", ["sqlmap", "-u", url, "--batch", "--crawl=1", "--level=1"],
                 timeout=1800, optional=True),
            Task("burpsuite",
                 note="GUI tool — launch with `tower`; Burp CE has no headless API to script"),
        ]
