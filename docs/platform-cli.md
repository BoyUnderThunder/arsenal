# Arsenal Platform CLI

`arsenal` is the unified command for the Arsenal platform. With no arguments it
prints the **armory** (the weapon registry); subcommands add diagnostics,
maintenance, support bundles, an AI assistant, multi-tool workflows, reporting,
curated profiles and a status dashboard.

Implementation: a stdlib-only Python package (`arsenal_cli`) installed at
`/usr/lib/arsenal`, launched by the `/usr/local/bin/arsenal` shim. Source and
tests live in `cli/` in the repo.

> For exact flags and exit codes of every subcommand, see
> [commands.md](commands.md). This page is the architectural overview.

## Commands (all shipped)

| Command | What it does | Details |
|---|---|---|
| `arsenal` / `armory` | Weapon registry table (`●` installed / `○` not on image). | [weapon-framework.md](weapon-framework.md) |
| `doctor` | 11 colour-coded health & security checks; exit ≠ 0 only on a failure. | below |
| `update` | Keyrings-first safe upgrade with rollback prep, verify, history. | [update.md](update.md) |
| `reportbug` | Redacted, compressed support bundle. | [troubleshooting.md](troubleshooting.md) |
| `recon` / `web` / `ad` | Multi-tool workflows into engagement projects (auth-gated). | [workflows.md](workflows.md) |
| `report` | Render a project to Markdown / HTML / PDF. | [commands.md](commands.md) |
| `profile` | Install curated toolsets (red/blue/forensics/reverse). | [commands.md](commands.md) |
| `ai` | Assistant over a swappable provider (Ollama / API). | [ai.md](ai.md) |
| `dashboard` | Dark status dashboard (XFCE launcher, or `--tui`). | [commands.md](commands.md) |

### `arsenal doctor`
System health & security diagnostics. Colour-coded `[✓]/[!]/[✗]/[i]` lines.
Exit code is non-zero only if a check **fails** (scriptable / CI-friendly).
Checks: hardened kernel, AppArmor, nftables (default-deny), BlackArch repo,
internet connectivity, disk space, memory, Arsenal version, pending updates,
package integrity (`pacman -Qkk`), critical services.

```text
[✓] Hardened kernel active        6.12-hardened1-1-hardened
[✓] AppArmor enabled              42 profiles
[✓] Firewall active (nftables, default-deny)
[!] Updates available             7 package(s) — run: arsenal update
[✓] BlackArch repository configured
```

## Global flags
- `--no-color` — disable ANSI colour (also honours `NO_COLOR` / `ARSENAL_NO_COLOR`).
- `-v, --verbose` — verbose logging to stderr (logs always go to
  `/var/log/arsenal/arsenal.log`, with safe fallbacks for non-root).
- `--version` — print the CLI version.

Exit codes: `0` success · `1` command-level failure · `2` usage/authorization
declined · `130` interrupted.

## Architecture
```
cli/arsenal_cli/
  __main__.py     # argparse dispatcher; `arsenal <command>`; _COMMANDS registry
  ui.py           # dark-theme colours, [✓]/[!]/[✗]/[i] badges, severity
  prompts.py      # shared confirm/--yes/EOF handling for mutating commands
  config.py       # /etc/arsenal + ~/.config/arsenal, well-known paths
  log.py          # rotating logs in /var/log/arsenal (safe fallbacks)
  runner.py       # safe subprocess wrapper (timeouts, missing-binary handling)
  version.py      # Arsenal OS version resolution
  project.py      # engagement-project model (arsenal.json + scans/loot/logs/report)
  commands/       # armory, doctor, update, reportbug, report, workflow,
                  #   profile, ai, dashboard
  workflows/      # base engine + recon / web / ad modules
  ai/             # provider ABC + ollama / openai_compat + assistant
  report/         # md / html / pdf renderers (dark theme)
  data/profiles/  # red / blue / forensics / reverse package lists
```

Adding a command = a module exposing `run(args) -> int` (plus `add_arguments`
if it takes options) and one line in `_COMMANDS` in `__main__.py`.
Adding a workflow = a `Workflow` subclass in `workflows/`; the base class
handles execution, recording, skips and report generation.

## Develop & test
```bash
cd cli
python -m unittest discover -s tests -t . -v   # stdlib only, no deps
ruff check .                                    # lint (config in pyproject.toml)
# or, if pytest is installed:
python -m pytest -q
```
CI runs the same lint + suite in `.github/workflows/ci-test.yml` on every
relevant push.
