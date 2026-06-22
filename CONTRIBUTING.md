# Contributing to Arsenal

Thanks for helping improve Arsenal — a white-hat security OS (Arch + BlackArch).

## Ground rules (read first)

1. **White-hat only.** Arsenal *integrates and brands existing open-source
   tools*. **Do not** contribute new exploit code, malware, backdoors,
   detection-evasion-for-evil, or anything whose primary purpose is unauthorized
   intrusion. Packaging/automation around legitimate, published FOSS tooling is
   welcome.
2. **Authorized-testing framing.** User-facing features that perform active
   testing must keep the authorization gate (see `commands/workflow.py`) and
   document the "authorized targets only" expectation.
3. **Security & privacy by default.** Don't weaken the Fortress defaults, don't
   exfiltrate user data, and keep `reportbug` redaction and the AI assistant's
   privacy posture intact.

## Project layout

```
build.sh              # ISO builder (archiso + BlackArch + branding)
tools/                # smoke-test.sh (+ future integration tests)
profile/              # the archiso overlay that becomes the ISO
  packages.x86_64     # toolkit package list
  airootfs/           # files overlaid onto the live system (identity, Fortress, Armory, desktop)
  airootfs/usr/local/share/arsenal/registry   # the weapon registry (single source of truth)
cli/arsenal_cli/      # the Python platform CLI
docs/                 # documentation
.github/workflows/    # build / test / boot / release CI
```

## Developing the CLI

```bash
cd cli
python -m unittest discover -s tests -t . -v   # stdlib only; must pass
ruff check .                                    # must be clean (pinned in CI)
```

The CLI is **stdlib-only** in its foundation; optional features must detect
their extras at runtime and degrade gracefully (never hard-crash because an
optional dep is missing).

### Adding a weapon (the Armory)
Append one line to
`profile/airootfs/usr/local/share/arsenal/registry`:
```
weapon|binary|Category|Short description
```
It automatically becomes a login launcher (`/etc/profile.d/arsenal-armory.sh`)
and a row in `arsenal armory` — no code change. Pick a weapon name that won't
clash with common commands.

### Adding a CLI command
Create `cli/arsenal_cli/commands/<name>.py` exposing `run(args) -> int` (and
`add_arguments(parser)` if it takes options), then register it in `_COMMANDS`
and the parser in `cli/arsenal_cli/__main__.py`. Add tests in `cli/tests/`.

### Adding a workflow
Create `cli/arsenal_cli/workflows/<name>.py` subclassing `Workflow` and
implementing `plan()`; wire a command in `commands/workflow.py`. The base class
handles execution, recording into the engagement project, graceful skips, and
report generation.

### Package names
Tool packages resolve at **build time** against `[core]/[extra]/[blackarch]`.
If a package is renamed or moves repos, `mkarchiso` fails on that exact line —
fix the name in `profile/packages.x86_64` (or the relevant
`cli/arsenal_cli/data/profiles/*.list`) and rebuild. Verify names against
<https://blackarch.org/tools.html> or `pacman -Ss`.

## Commits & pull requests

- Keep changes focused; write a clear commit subject + body explaining *why*.
- Run the CLI tests and `ruff check .` before pushing; CI runs them plus
  ShellCheck and (for ISO-affecting changes) a full build + QEMU boot test.
- Don't commit build artifacts (`work/`, `out/`, `*.iso`) — they're gitignored.
- Open a PR against `main`. Describe what you changed and how you verified it.
- By contributing you affirm your contribution complies with the ground rules
  above and is yours to license under the project's terms.

## Reporting bugs vs. vulnerabilities

- **Bugs / features:** open a GitHub issue.
- **Security vulnerabilities:** do **not** open a public issue — follow
  [SECURITY.md](SECURITY.md).
