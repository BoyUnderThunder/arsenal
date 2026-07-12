# Changelog

All notable changes to Arsenal are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); releases use the
project's calendar tags (`vYYYY.MM.DD`, see [RELEASING.md](RELEASING.md)).

Because the ISO tracks rolling Arch + BlackArch, this log covers Arsenal's own
platform — the builder, the Fortress hardening baseline, the Armory, the
`arsenal` CLI, provenance, and CI — not the version bumps of bundled tools
(those are captured per-build in the SBOM and lockfile).

## [Unreleased]

### Added
- **Findings/severity model in engagement reports.** Workflows can now surface
  structured `Finding`s (title, severity critical→info, target, evidence, refs)
  alongside the step log; reports render a severity-sorted **Findings** section
  with counts in both Markdown and HTML, and the recon workflow turns nmap's
  open ports into findings. Persisted in `arsenal.json` (old projects still
  load). Turns a report from a step-list into an assessment.
- **Supply-chain provenance.** Every build emits a lockfile plus
  [CycloneDX](https://cyclonedx.org/) 1.5 and [SPDX](https://spdx.dev/) 2.3
  SBOMs (`tools/gen_sbom.py`) generated from the built image's own pacman
  database, and `tools/verify-sbom.py` validates that those artifacts are
  well-formed and mutually consistent (the build self-checks them).
- **Reproducible builds.** `build.sh` pins the Arch repositories to a dated
  [Arch Linux Archive](https://archive.archlinux.org/) snapshot (after
  BlackArch's `strap.sh`), so rebuilds from a commit resolve the same package
  versions. Controlled by `ARSENAL_ARCH_SNAPSHOT`.
- **Release verification.** `tools/verify-release.sh` checks a download's
  `SHA256SUMS` manifest and GPG signature (when present), reassembles the split
  ISO, and verifies the whole-image checksum. Release signing scaffolding is in
  place (`GPG_PRIVATE_KEY` / `GPG_PASSPHRASE`); releases publish unsigned until
  a key is configured.
- **`arsenal doctor` hardening posture checks** — kernel-hardening sysctls,
  blacklisted-module load detection, AppArmor-enforced-profile count, and a
  network-exposure check (services listening beyond loopback) — plus
  `arsenal doctor --json` for machine-readable output.
- **`arsenal armory`** — `--json` machine-readable inventory, a positional
  query that filters weapons by name/tool/category/description, and
  `--installed` / `--missing` to filter by whether the tool is on the image.
  The table and `--json` now render from one shared inventory (which the
  dashboard's weapon count reuses too), so the views can't drift.
- **Seven Armory weapons** — `howitzer` (masscan) and `prospector` (binwalk),
  plus `dissector` (radare2), `smith` (john), `vivisector` (gdb), `wiretap`
  (tcpdump) and `ghost` (proxychains) surfacing tools already in the image.
- **Bash tab-completion** for the `arsenal` CLI (subcommands + options) on the
  live image.
- **`man arsenal`** — a manual page on the live image, kept in lock-step with
  the CLI by a drift-guard test and mandoc-linted in CI.
- **Developer tooling.** `tools/preflight.sh` runs the CI fast-checks (ruff,
  CLI + provenance tests, ShellCheck) locally before pushing; a registry
  invariant test guards the weapon registry (4 fields, unique names, no
  shadowing of critical commands) so a bad entry fails CI, not the ISO.

### Changed
- CI runs a hardening self-test / integration gate on each build; `ci-test`
  lints and tests all of `cli/` and `tools/`.

### Performance
- **`arsenal doctor`** runs its checks concurrently on a thread pool instead of
  serially. They are independent and almost all I/O-bound (sysctl / ss / pacman
  / aa-status), so wall time drops to about the single slowest check — a large
  speedup dominated by `pacman -Qkk` and `checkupdates`. Order and failure
  isolation are unchanged.
- **Faster ISO build + boot.** The airootfs squashfs now uses zstd (level 19)
  instead of releng's xz: several times faster to compress (shorter builds) and
  much faster to decompress (snappier live boot), at a near-identical size and
  still deterministic. Set `ARSENAL_SQUASHFS_COMP=off` to keep xz.

### Security
- **`auditd` is now enabled** on the live image (it shipped installed but
  inert). AppArmor denials and kernel audit events are logged from boot, and
  `arsenal doctor` reports the daemon's state.

### Fixed
- Build resilience: the post-strap package-DB sync now retries with backoff
  instead of aborting the whole ~50-minute build the first time a (rolling
  BlackArch) mirror times out mid-refresh.

## [v2026.06.22]

Initial public release — the Arsenal live ISO (Arch Linux + BlackArch): the
Fortress hardening baseline (hardened kernel, AppArmor, nftables default-deny,
audit), the Armory weapon framework, the dark XFCE desktop, and the `arsenal`
platform CLI (armory, doctor, update, reportbug, report, workflows, AI
assistant).

[Unreleased]: https://github.com/BoyUnderThunder/arsenal/compare/v2026.06.22...HEAD
[v2026.06.22]: https://github.com/BoyUnderThunder/arsenal/releases/tag/v2026.06.22
