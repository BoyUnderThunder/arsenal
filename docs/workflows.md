# Workflow Engine

High-level commands that orchestrate multiple tools, record structured results
into an **engagement project**, and render a report.

## Commands
```bash
arsenal recon <host|cidr|url>      # nmap -> gobuster content discovery (needs a wordlist)
arsenal web   <url>                # nikto + sqlmap (+ Burp hand-off note)
arsenal ad    <domain> --user U --password P [--dc-ip IP]
```
Flags: `--dry-run` (print the plan), `-y/--yes` (skip the authorization prompt),
`--name`, `-o/--output` (engagement base dir). `recon` adds `--wordlist`.

> **Authorization:** active workflows prompt for confirmation before running.
> Non-interactive use requires `-y`. Only test systems you are authorized to test.

## Engagement projects
Each run creates `~/engagements/<name>-<timestamp>/`:
```
arsenal.json     # metadata + per-step results (machine readable)
scans/           # raw tool output (one file per step)
loot/  logs/     # for your artifacts
report/          # report.md + report.html (auto-generated)
```
Render anytime: `arsenal report ~/engagements/<dir>`.

## Findings
Beyond the step log, a workflow can emit structured **findings** — the unit that
makes a report an *assessment*. A `Finding` has a `title`, `severity`
(`critical` › `high` › `medium` › `low` › `info`), `target`, `evidence`, and
optional `refs`. A task produces them with a `find=` callable:
```python
Task("nmap", ["nmap", "-sV", host], summarize=..., find=my_producer)
# my_producer(res) -> list[Finding]
```
Findings are stored in `arsenal.json` and rendered as a severity-sorted
**Findings** section (with counts) in both the Markdown and HTML reports. The
`recon` workflow already turns nmap's open ports into `info` findings.

## Graceful behaviour
- Missing tool → step **skipped** (not failed) with a note.
- Missing wordlist (recon) → web discovery skipped with guidance
  (`install seclists` or `--wordlist`).
- AD without creds → BloodHound/Impacket steps skipped with guidance.
- Burp Suite (CE, no API) → recorded as a manual step pointing at `tower`.

## Adding a workflow
Create `cli/arsenal_cli/workflows/<name>.py`:
```python
from .base import Task, Workflow

class MyWorkflow(Workflow):
    kind = "myflow"
    def plan(self):
        return [Task("nmap", ["nmap", "-sV", self.target], summarize=...)]
```
Wire a command in `commands/workflow.py` and register it in `__main__.py`.
The base class handles execution, recording, skips, and the report.
