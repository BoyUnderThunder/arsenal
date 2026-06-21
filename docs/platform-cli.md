# Arsenal Platform CLI

`arsenal` is the unified command for the Arsenal platform. With no arguments it
prints the **armory** (the weapon registry); subcommands add diagnostics,
maintenance, support bundles and more.

Implementation: a stdlib-only Python package (`arsenal_cli`) installed at
`/usr/lib/arsenal`, launched by the `/usr/local/bin/arsenal` shim. Source and
tests live in `cli/` in the repo.

## Commands

### `arsenal` / `arsenal armory`
Prints the weapon registry (weapon → tool → category → description) with an
`●`/`○` indicator showing which tools are installed on the running image. Reads
`/usr/local/share/arsenal/registry` — the same file that drives the profile.d
weapon launchers, so the two never drift.

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

### `arsenal reportbug [--no-redact] [-o FILE]`
Builds a compressed support bundle: `journalctl -b`, `dmesg`, hardware info
(`lscpu`/`lspci`/`inxi`), package list, running/failed services and the Arsenal
version. Sensitive data (IPv4/IPv6/MAC addresses, secrets) is **redacted by
default**; pass `--no-redact` to keep it. Output: `/tmp/arsenal-report-<ts>.tar.zst`
(falls back to `.tar.gz` if `zstd` is unavailable).

## Global flags
- `--no-color` — disable ANSI colour.
- `-v, --verbose` — verbose logging to stderr (logs always go to
  `/var/log/arsenal/arsenal.log`).
- `--version` — print the CLI version.

## Architecture
```
cli/arsenal_cli/
  __main__.py     # argparse dispatcher; `arsenal <command>`
  ui.py           # dark-theme colours, [✓]/[!]/[✗]/[i] badges, severity
  config.py       # /etc/arsenal + ~/.config/arsenal, well-known paths
  log.py          # rotating logs in /var/log/arsenal (safe fallbacks)
  runner.py       # safe subprocess wrapper (timeouts, missing-binary handling)
  version.py      # Arsenal OS version resolution
  commands/       # armory, doctor, reportbug (more in later phases)
```
Adding a command = a module exposing `run(args) -> int` plus one line in
`_COMMANDS` in `__main__.py`.

## Develop & test
```bash
cd cli
python -m unittest discover -s tests -t . -v   # stdlib only
```
CI runs the same suite in `.github/workflows/ci-test.yml` on every relevant push.

## Roadmap (later phases)
`arsenal report` (md/html/pdf) · `arsenal recon|web|ad` (workflow engine) ·
`arsenal profile red|blue|forensics|reverse` · `arsenal update` (with rollback
prep) · `arsenal ai` (Ollama / API providers) · `arsenal dashboard` (XFCE).
