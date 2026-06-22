# Security Policy

Arsenal is a **white-hat** security operating system. It assembles, brands and
orchestrates existing open-source tools; it ships **no new exploit code**. This
policy covers vulnerabilities in **Arsenal itself** — the ISO composition, the
`arsenal` CLI, the build/release pipeline and the hardening defaults.

## Scope

**In scope** (report to us):
- The `arsenal` platform CLI (`cli/arsenal_cli`) — e.g. command injection,
  unsafe file handling, redaction bypass in `reportbug`, the AI assistant
  sending data it shouldn't.
- The ISO overlay and hardening (`profile/airootfs/**`) — e.g. a firewall/AppArmor
  default that fails open, an insecure service enabled, a weak permission.
- The build & release supply chain (`build.sh`, `tools/**`,
  `.github/workflows/**`, `RELEASING.md`) — e.g. an unverified download,
  a tampering vector, a signing gap.

**Out of scope** (report upstream):
- Vulnerabilities in the **bundled third-party tools** (nmap, metasploit,
  Burp, ghidra, BlackArch packages, the Linux kernel, …). Report those to the
  respective upstream project, BlackArch, or Arch.
- Findings produced **by** Arsenal's tools against **your** targets — that is
  the tooling working as intended.
- Misuse of Arsenal against systems you are not authorized to test (see ethos).

## Reporting a vulnerability

**Please do not open a public issue for a security vulnerability.**

Use **GitHub's private vulnerability reporting**:
**Repository → Security → "Report a vulnerability"**
(https://github.com/BoyUnderThunder/arsenal/security/advisories/new).

Include: affected component/version (ISO tag or commit, or `arsenal --version`),
a clear description, reproduction steps, and impact. A proof-of-concept is
welcome but never required.

### What to expect
- **Acknowledgement:** within ~5 days.
- **Triage & severity:** we'll confirm the issue and assess impact.
- **Fix & disclosure:** we'll work on a fix and coordinate a disclosure
  timeline with you, crediting you unless you prefer otherwise. Please allow a
  reasonable window before any public disclosure.

## Supported versions

Arsenal tracks rolling Arch + BlackArch. Security fixes target the **latest
release** and `main`. Older release tags are snapshots and are not patched in
place — upgrade (`arsenal update`) or move to the newest release.

## Verifying downloads

Each release publishes a SHA-256 checksum of the image (`*.iso.sha256`); once
release signing is enabled it will also publish `SHA256SUMS.asc` and per-part
signatures. Always verify the checksum — and signatures when present — before
writing the image. See the release notes and [RELEASING.md](RELEASING.md).

## Ethos

Arsenal is for **authorized testing only** — systems you own or have explicit
written permission to assess. The maintainers do not support, and will not
assist with, unauthorized or unlawful use. You are responsible for staying
within scope and the law.
