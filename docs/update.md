# Update & Rollback

`arsenal update` performs safe system maintenance on the rolling Arch +
BlackArch base.

## Usage
```bash
arsenal update --check     # list pending updates, change nothing
sudo arsenal update        # full upgrade (prompts unless -y)
sudo arsenal update -y --no-snapshot
```

## What it does
1. **Pending check** — via `checkupdates` (no root, safe) or `pacman -Qu`.
2. **Rollback prep** — saves pre-update state to
   `/var/log/arsenal/updates/<timestamp>/`:
   - `explicit-packages.txt`, `all-packages.txt` (with versions)
   - `ROLLBACK.txt` (how to downgrade)
   - a **Timeshift** snapshot if `timeshift` is installed (skip with `--no-snapshot`).
3. **Keyrings first** — `archlinux-keyring` (+ `blackarch-keyring`) before the
   main upgrade, to avoid signature failures / partial-upgrade breakage.
4. **Full upgrade** — `pacman -Syu` (never a partial upgrade).
5. **Verification** — checks the armory registry, hardened kernel and core
   services after upgrading.
6. **History** — appends a line to `/var/log/arsenal/updates/history.log`.

## Rolling back
Arch has no true transactional rollback. To revert a package, reinstall the
cached version:
```bash
pacman -U /var/cache/pacman/pkg/<name>-<oldversion>.pkg.tar.zst
```
Use `all-packages.txt` from the relevant `updates/<timestamp>/` dir to find the
previous version. If you took a Timeshift snapshot, restore it with `timeshift`.

> A new `linux-hardened` may require a **reboot**; `arsenal doctor` will warn if
> the running kernel differs from the installed one.
