# Arsenal Commands

`arsenal <command> [options]`. Global flags: `--no-color`, `-v/--verbose`,
`--version`. With no command, prints the armory. Logs: `/var/log/arsenal/arsenal.log`.

## `armory` (default)
Print the weapon registry (weapon → tool → category → description) with `●`/`○`
showing installed tools. See [weapon framework](weapon-framework.md).

## `doctor`
System health & security diagnostics. Colour-coded `[✓]/[!]/[✗]/[i]`; exit code
is non-zero only on a failed check. Checks: hardened kernel, AppArmor, nftables
(default-deny), BlackArch repo, internet, disk, memory, version, pending updates,
package integrity, critical services.

## `update [--check] [-y] [--no-snapshot]`
Refresh repos and upgrade packages safely. See [update & rollback](update.md).
- `--check` — list pending updates only (no changes).
- `-y` — no confirmation prompt. `--no-snapshot` — skip the Timeshift hook.
- Requires root for the actual upgrade.

## `reportbug [--no-redact] [-o FILE]`
Collect a compressed support bundle (journalctl, dmesg, hardware, packages,
services, version). Sensitive data redacted by default. See
[troubleshooting](troubleshooting.md).

## `ai [PROMPT…] [--tool T] [--log FILE] [--provider P] [--model M]`
Ask the AI assistant. See [AI assistant](ai.md).

## `recon|web|ad <target> [-y] [--dry-run] [--name N] [-o DIR]`
Run a multi-tool workflow into an engagement project. Active testing requires an
authorization confirmation (or `-y`). See [workflows](workflows.md).
- `recon` adds `--wordlist`. `ad` adds `--user/--password/--dc-ip`.

## `report <project> [-f md|html|pdf|all] [-o DIR]`
Render an engagement project (`arsenal.json`) to Markdown / HTML / PDF (PDF via
WeasyPrint if installed).

## `profile [<name>|list] [--show] [-y]`
Install a curated toolset: `red`, `blue`, `forensics`, `reverse`. `list` shows
profiles; `--show` lists packages without installing. Install requires root.

## `dashboard [--tui] [--no-open] [-o FILE]`
Generate/open the dark status dashboard (XFCE launcher provided), or render it
in the terminal with `--tui`.

## Exit codes
`0` success · `1` command-level failure (e.g. a failed doctor check, missing
project) · `2` usage/authorization declined · `130` interrupted.
