# Troubleshooting

## First step: diagnostics
```bash
arsenal doctor          # colour-coded health & security checks
arsenal doctor -v       # with verbose logging to stderr
```
Exit code is non-zero if any check **fails**. Investigate `[✗]`/`[!]` lines.

## Logs
- CLI logs: `/var/log/arsenal/arsenal.log` (rotating; falls back to
  `~/.local/state/arsenal` or `/tmp/arsenal` for non-root).
- Update history: `/var/log/arsenal/updates/history.log`.
- System: `journalctl -b`, `dmesg`.

## Support bundle
```bash
arsenal reportbug                 # redacted .tar.zst in /tmp
arsenal reportbug --no-redact     # keep IPs/MACs/secrets (be careful)
arsenal reportbug -o ./bundle.tar.zst
```
Redaction masks IPv4/IPv6/MAC addresses and obvious secrets. **Always review a
bundle before sharing it.**

## Common issues
| Symptom | Check |
|---|---|
| `weapon: not installed` | `pacman -S <tool>` (BlackArch is enabled) |
| `arsenal ai` says unavailable | start Ollama or set `ARSENAL_AI_KEY` — see [ai.md](ai.md) |
| recon skips web discovery | no wordlist — `pacman -S seclists` or `--wordlist` |
| `arsenal report` PDF skipped | `pacman -S python-weasyprint` (MD/HTML always work) |
| firewall check fails | `systemctl enable --now nftables` |
| kernel check fails after update | reboot into the new `linux-hardened` |
| `profile`/`update` say root required | re-run with `sudo` |

## Reset CLI config
Remove user overrides: `rm -f ~/.config/arsenal/arsenal.conf` (system defaults
in `/etc/arsenal/arsenal.conf` remain).
