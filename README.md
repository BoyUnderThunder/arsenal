# Arsenal — a white-hat security OS

Arsenal is a custom Arch-based live ISO built with **archiso** on top of the
**BlackArch** repository. It bundles a curated, best-of-all-worlds white-hat
toolkit (red, blue, forensics, reversing, recon), brands every tool behind a
memorable *weapon* name (**The Armory**), and ships hardened by default
(**The Fortress**): the `linux-hardened` kernel, AppArmor, a default-deny
`nftables` firewall, and LUKS-ready initramfs.

> **Authorized testing only.** Arsenal assembles existing, legitimate
> open-source tools. Use it on systems you own or are explicitly permitted to
> test. Know your local law.

---

## How it's built (and why not in every sandbox)

`mkarchiso` downloads hundreds of packages from the **Arch** and **BlackArch**
mirrors. Any environment with a locked-down network egress allowlist (some
cloud/CI sandboxes block everything except a few hosts) **cannot** run the
build — the mirrors return HTTP 403. The build therefore runs where those
mirrors are reachable. Three supported paths, in order of convenience:

### 1. GitHub Actions (recommended — no local Arch needed)

`.github/workflows/build-iso.yml` builds the ISO inside a privileged
`archlinux` container on a GitHub-hosted runner (open network), boot-tests it
in QEMU, and uploads the ISO as an artifact.

- Push to any branch that touches `profile/`, `build.sh`, or `tools/`, **or**
- Run it manually: **Actions → build-arsenal-iso → Run workflow** (choose
  `full` or `lean`).

Download the finished ISO from the run's **Artifacts**.

### 2. On a real Arch Linux box

```bash
sudo ./build.sh                 # full toolkit
sudo ARSENAL_PROFILE=lean ./build.sh   # smaller/faster build
```

The script installs `archiso`, runs BlackArch's `strap.sh`, assembles the
profile, and runs `mkarchiso`. The ISO lands in `./out/`.

### 3. On any Linux with Docker (privileged container)

```bash
docker run --privileged --rm -v "$PWD":/repo -e ARSENAL_SERIAL=1 \
  archlinux:latest bash -c 'pacman-key --init && cd /repo && ./build.sh'
```

### Boot test

```bash
sudo tools/smoke-test.sh out/arsenal-*.iso     # headless boot check
# or interactively (with a display):
qemu-system-x86_64 -m 4096 -smp 2 -cdrom out/arsenal-*.iso -boot d
```

`smoke-test.sh` loop-mounts the ISO, extracts `vmlinuz-linux-hardened` + the
initramfs, and boots them directly in QEMU (KVM if available, else TCG) with a
forced serial console, attaching the ISO as a CD so the archiso initramfs finds
the squashfs by label. It passes only when the system reaches its autologin
`root@arsenal` shell (verified markers, not bootloader branding). Needs root to
mount the ISO.

---

## Repository layout

```
build.sh                     # assembles releng + overlay, wires BlackArch, runs mkarchiso
tools/smoke-test.sh          # QEMU boot test
.github/workflows/build-iso.yml
profile/
├── packages.x86_64          # Arsenal package additions (appended to releng's list)
├── packages.lean.drop       # packages removed for the "lean" flavor
├── pacman-blackarch.conf     # [blackarch] stanza added to the build's pacman.conf
└── airootfs/                # files overlaid onto the live filesystem
    ├── etc/os-release            # OS identity: Arsenal
    ├── etc/hostname              # arsenal
    ├── etc/motd, etc/issue       # dark branding
    ├── etc/profile.d/arsenal-armory.sh   # weapon launchers (The Armory)
    ├── etc/nftables.conf         # default-deny firewall (The Fortress)
    ├── etc/sysctl.d/…            # kernel hardening
    ├── etc/modprobe.d/…          # blacklisted modules
    ├── etc/mkinitcpio.*          # linux-hardened + LUKS-ready initramfs
    ├── etc/pacman.conf, pacman.d/blackarch-mirrorlist   # BlackArch on the live system
    ├── usr/local/bin/arsenal     # the `arsenal` registry command
    ├── usr/local/share/arsenal/registry   # single source of truth for weapons
    └── root/…                    # dark XFCE session + theme
```

`build.sh` copies the system's `releng` profile as the base, overlays
`profile/airootfs/`, merges `profile/packages.x86_64`, swaps in the
`linux-hardened` kernel, brands the boot menus/`profiledef.sh`, and appends the
`[blackarch]` repo before calling `mkarchiso`.

---

## The Armory

Every weapon name launches its real tool, passing arguments straight through.
Run **`arsenal`** to print the registry:

| Weapon        | Tool          | Category         | What it does                         |
|---------------|---------------|------------------|--------------------------------------|
| `sniper`      | nmap          | Recon            | Network mapper & port/service scanner|
| `bazooka`     | msfconsole    | Exploitation     | Metasploit Framework console         |
| `tower`       | burpsuite     | Web              | Burp Suite — web proxy & scanner     |
| `tank`        | hydra         | Passwords        | THC Hydra — online login brute-forcer|
| `breaker`     | hashcat       | Passwords        | hashcat — GPU/CPU hash cracker       |
| `masterkey`   | sqlmap        | Web              | sqlmap — automatic SQL injection     |
| `agent`       | aircrack-ng   | Wireless         | aircrack-ng — Wi-Fi 802.11 auditing  |
| `overseer`    | wireshark     | Monitor          | Wireshark — protocol analyzer        |
| `hunter`      | bloodhound    | Active Directory | BloodHound — AD attack-path mapping  |
| `scalpel`     | ghidra        | Reversing        | Ghidra — reverse engineering suite   |
| `detective`   | vol           | Forensics        | Volatility 3 — memory forensics      |
| `interrogator`| autopsy       | Forensics        | Autopsy — digital forensics platform |

Example: `sniper -sV 10.0.0.0/24` runs `nmap -sV 10.0.0.0/24`.

The registry (`/usr/local/share/arsenal/registry`) drives both the launchers
and the `arsenal` command, so they never drift.

> **BloodHound DB:** the `bloodhound` package is included; modern BloodHound CE
> brings its own backend. If you run the legacy edition that needs a Neo4j
> database, install one in the live session (`pacman -S` from the AUR/your
> mirror) — Arsenal intentionally doesn't ship a heavyweight DB by default.

---

## The Platform CLI (`arsenal <command>`)

Beyond the armory, `arsenal` is a full platform CLI (Python, in `cli/`,
installed to `/usr/lib/arsenal`):

- **`arsenal` / `armory`** — the weapon registry table.
- **`arsenal doctor`** — colour-coded health & security diagnostics.
- **`arsenal update`** — safe upgrade with keyrings-first, rollback prep & verify.
- **`arsenal reportbug`** — redacted, compressed support bundle.
- **`arsenal recon|web|ad <target>`** — multi-tool workflows into engagement projects.
- **`arsenal report <project>`** — Markdown/HTML/PDF reports.
- **`arsenal profile red|blue|forensics|reverse`** — install curated toolsets.
- **`arsenal ai`** — AI assistant (local Ollama or API), swappable providers.
- **`arsenal dashboard`** — dark status dashboard (XFCE launcher / `--tui`).

Full docs: **[docs/](docs/README.md)**. CLI source + tests in `cli/`
(`.github/workflows/ci-test.yml` runs `python -m unittest`).

---

## The Fortress (hardening)

- **`linux-hardened`** kernel (replaces stock `linux`).
- **AppArmor** enabled at boot (`apparmor=1 security=apparmor lsm=…apparmor…`)
  and via `apparmor.service`.
- **Default-deny `nftables`** firewall (`/etc/nftables.conf`): inbound dropped
  except loopback/established/ICMP; no exposed services. Enabled via
  `nftables.service`.
- **LUKS-ready** initramfs (`encrypt` + `lvm2` hooks) and `cryptsetup`/`lvm2`
  installed, so you can boot from / install onto encrypted volumes.
- **sysctl** hardening (`kptr_restrict`, `dmesg_restrict`, `ptrace_scope`,
  reverse-path filtering, …) and a **module blacklist** for legacy/abusable
  modules.

---

## Customizing

- **Add a tool:** put its package name in `profile/packages.x86_64`. Verify the
  exact name against the repos (`pacman -Ss <name>` once booted, or
  <https://blackarch.org/tools.html>).
- **Add a weapon:** add a `weapon|binary|category|description` line to
  `profile/airootfs/usr/local/share/arsenal/registry`. The launcher and the
  `arsenal` command pick it up automatically.
- **Theme:** edit the XFCE/GTK files under `profile/airootfs/root/.config` and
  `etc/skel`.
- **Kernel cmdline / branding:** see steps 4–6 in `build.sh`.
- **Smaller image:** build the `lean` flavor (drops the heavy GUI/Java/DB tools
  listed in `profile/packages.lean.drop`).

### A note on package names

Names are resolved at build time against `[core]`, `[extra]`, and
`[blackarch]`. If a tool is renamed or moves between repos, `mkarchiso` fails
on that exact line — read the error, fix the name in `profile/packages.x86_64`,
and rebuild. That tight error→fix→rebuild loop is expected and normal for a
BlackArch-based image.
