# Arsenal Threat Model

This document states, plainly, **what Arsenal defends against**, **what it
explicitly does not**, and the **authorized-testing-only** scope it operates
under. It is deliberately honest: Arsenal is an *offensive toolkit on a hardened
base*, not a fortress for hostile environments.

## Who Arsenal is for
An authorized security professional ("the operator") running assessments on
systems they own or have **explicit written permission** to test. The operator
is trusted; their workstation is the asset Arsenal hardens.

## What Arsenal defends (the operator's own machine)

| Asset / surface | Defence | Where |
|---|---|---|
| Inbound network attack surface | Default-deny `nftables` (drop input/forward; no exposed services) | `etc/nftables.conf` |
| Kernel exploit surface | `linux-hardened` kernel; AppArmor (enforced via cmdline + service); restrictive `sysctl` (kptr/dmesg/ptrace/bpf/perf, rp_filter, syncookies); legacy/abusable module blacklist | `profile/airootfs/etc/*`, `build.sh` |
| Data at rest | LUKS-ready initramfs (`encrypt`+`lvm2`), `cryptsetup`/`lvm2` installed — boot from / install onto encrypted volumes | `etc/mkinitcpio.conf.d/arsenal.conf` |
| DMA / physical side channels | FireWire/Thunderbolt modules blacklisted | `etc/modprobe.d/arsenal-blacklist.conf` |
| Accidental data leak in support bundles | `arsenal reportbug` redacts IPv4/IPv6/MAC/secrets by default | `cli/.../commands/reportbug.py` |
| Self-diagnosis / drift detection | `arsenal doctor` verifies the posture at runtime (kernel, AppArmor, firewall, services, integrity) | `cli/.../commands/doctor.py` |
| Release integrity | Published image checksum (`*.iso.sha256`); signatures + `SHA256SUMS` and pinned/verified build inputs (roadmap: Tier 1) | `RELEASING.md`, `build.sh` |

Verify any time with `arsenal doctor`, `aa-status`, `nft list ruleset`.

## What Arsenal explicitly does NOT defend against (non-goals)

- **A malicious or careless operator.** Arsenal does not stop you from doing
  harm. It does not vet your targets, check your authorization, or sandbox the
  tools from each other.
- **Misuse against unauthorized targets.** Out of scope and unsupported. The
  authorization gate on active workflows is a speed bump and a reminder, **not**
  an access-control system.
- **The danger of the bundled tools themselves.** nmap, metasploit, responder,
  hashcat, etc. are **dual-use and powerful by design**. Running them affects
  *other* systems; that risk is inherent and intentional, not a flaw.
- **A hostile multi-user / server deployment.** Arsenal is a single-operator
  workstation/live OS, not a hardened internet-facing server. The live image
  autologins root for usability.
- **Anti-forensics / plausible deniability.** Arsenal is not designed to hide
  its own or the operator's activity. Logs, engagement projects and tool output
  are written to disk.
- **A fully reproducible, frozen software bill of materials by default.**
  BlackArch is rolling; a live boot pulls current packages. Reproducibility is
  addressed per-release via lockfiles/SBOM (roadmap: Tier 1), not in the live
  image.
- **Confidentiality of data sent to a remote AI provider.** `arsenal ai`
  defaults to **local** Ollama; choosing a remote API sends your prompt/context
  to that provider. Treat that as data leaving the machine.

## Trust boundaries

- **Tool output is untrusted input.** Scan results, banners and web responses
  are attacker-controllable. Anything that re-processes them (notably the AI
  assistant) must treat them as *data, never instructions* — they are a
  prompt-injection vector. (Hardening this is tracked in the roadmap.)
- **Downloaded build inputs are untrusted** until verified (checksums/keys).
- **The network is hostile;** Arsenal exposes no services by default.

## Authorized-testing-only scope

Use Arsenal **only** on systems you own or are explicitly authorized to test.
Know and follow your local law and the rules of engagement. The maintainers
provide Arsenal for lawful, professional security work and do not support
unauthorized use. See [SECURITY.md](../SECURITY.md) and the README's
authorization notice.
