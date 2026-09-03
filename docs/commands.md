# Arsenal Commands

`arsenal <command> [options]`. Global flags: `--no-color`, `-v/--verbose`,
`--version`. With no command, prints the armory. Logs: `/var/log/arsenal/arsenal.log`.
Bash tab-completion for subcommands and options ships on the live image.

## `armory [QUERY] [--installed|--missing] [--json]` (default)
Print the weapon registry (weapon → tool → category → description) with `●`/`○`
showing installed tools. See [weapon framework](weapon-framework.md).
- `QUERY` — filter to weapons whose name/tool/category/description contains the
  term (case-insensitive), e.g. `arsenal armory web`.
- `--installed` / `--missing` — filter by whether the tool is present on this
  image (combines with `QUERY`).
- `--json` — machine-readable inventory (`{weapons[], count}`, each weapon with
  `installed`) for scripting and dashboards.

## `doctor [--json]`
System health & security diagnostics. Colour-coded `[✓]/[!]/[✗]/[i]`; exit code
is non-zero only on a failed check. Checks: hardened kernel, AppArmor, nftables
(default-deny), kernel-hardening sysctls, module blacklist, AppArmor enforce
mode, BlackArch repo, internet, network exposure (listening services), disk,
memory, version, pending updates, package integrity, critical services, audit
daemon.
- `--json` — machine-readable output (`{checks[], summary, ok}`) for monitoring
  or scripting; same exit code as the human view.

## `update [--check] [-y] [--no-snapshot]`
Refresh repos and upgrade packages safely. See [update & rollback](update.md).
- `--check` — list pending updates only (no changes).
- `-y` — no confirmation prompt. `--no-snapshot` — skip the Timeshift hook.
- Requires root for the actual upgrade.

## `reportbug [--no-redact] [-o FILE]`
Collect a compressed support bundle (journalctl, dmesg, hardware, packages,
services, version). Sensitive data redacted by default. See
[troubleshooting](troubleshooting.md).

## `ai [PROMPT…] [--tool T] [--log FILE] [--summarize PROJECT] [--provider P] [--model M]`
Ask the AI assistant. `--summarize <project>` writes an executive summary into an
engagement (from its redacted findings/steps — never raw scan output); regenerate
the report to include it. See [AI assistant](ai.md).

## `recon|web|ad <target> [-y] [--dry-run] [--name N] [-o DIR]`
Run a multi-tool workflow into an engagement project. Active testing requires an
authorization confirmation (or `-y`). See [workflows](workflows.md).
- `recon` adds `--wordlist`. `ad` adds `--user/--password/--dc-ip`.

## `report <project> [-f md|html|pdf|all] [-o DIR]`
Render an engagement project (`arsenal.json`) to Markdown / HTML / PDF (PDF via
WeasyPrint if installed).

## `engagements [list|show|rerun|delete|archive] [DIR] [-y] [-o OUT]`
Manage recorded engagement projects under `~/engagements`: `list` (default) all
of them, `show` one, `rerun` its workflow (with the authorization prompt),
`archive` it to a tarball, or `delete` it. See [workflows](workflows.md).

## `secret-agent [on|off|status] [--cloak] [--no-trace] [--tor] [--disguise] [-y]`
Operator OPSEC ("go covert") mode — protects **you** during authorized work, not
the systems under test. `on` enables all four capabilities (or only the ones you
flag): **cloak** (randomize interface MACs, clock→UTC, spoof hostname),
**no-trace** (disable swap, shell history off, clear logs), **tor** (route
everything through Tor with an nftables kill-switch — clearnet/DNS/IPv6 leaks
blocked), and **disguise** (generic desktop look). `off` restores the Fortress
defaults; `status` shows what's active. `on`/`off` require root.

## `profile [<name>|list] [--show] [-y]`
Install a curated toolset: `red`, `blue`, `forensics`, `reverse`. `list` shows
profiles; `--show` lists packages without installing. Install requires root.

## `dashboard [--tui] [--no-open] [-o FILE]`
Generate/open the dark status dashboard (XFCE launcher provided), or render it
in the terminal with `--tui`.

## Exit codes
`0` success · `1` command-level failure (e.g. a failed doctor check, missing
project) · `2` usage/authorization declined · `130` interrupted.
