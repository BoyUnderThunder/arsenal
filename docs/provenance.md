# Provenance & supply chain

Arsenal aims to be **auditable** and **reproducible**: you can see exactly what
shipped in an image, rebuild it, and verify a download end-to-end.

## Reproducible builds

`build.sh` pins the Arch repositories to a dated
[Arch Linux Archive](https://archive.archlinux.org/) (ALA) snapshot before
`mkarchiso` runs, so a rebuild from the same commit resolves the **same** Arch
package versions instead of whatever rolling Arch happens to serve that day.

- Controlled by `ARSENAL_ARCH_SNAPSHOT` (default set in `build.sh`,
  `YYYY/MM/DD`). Set `ARSENAL_ARCH_SNAPSHOT=off` to build against rolling Arch.
- The pin is applied **after** BlackArch's `strap.sh` (which fetches its own
  mirror list), and the effective `[core]` mirror is logged during the build.
- BlackArch has no dated archive, so it stays rolling; the small skew against
  the pinned Arch base is harmless in practice.

## What every build emits

Alongside the ISO, each CI build produces an **`arsenal-provenance`** artifact
(see `build-iso.yml`), generated from the built image's own pacman database —
the full dependency closure, not just the explicit package list:

| File | What it is |
|------|------------|
| `<iso>.lock` | Sorted `name version` of every installed package. Stable across builds for clean diffs. |
| `<iso>.cdx.json` | [CycloneDX](https://cyclonedx.org/) 1.5 SBOM, one `pkg:alpm` component per package. |
| `<iso>.spdx.json` | [SPDX](https://spdx.dev/) 2.3 SBOM, same package set. |

Both SBOMs record the ALA snapshot in their document metadata. The generator is
`tools/gen_sbom.py` (stdlib-only, unit-tested in `tools/test_gen_sbom.py`).

At release time, `release.yml` commits the released build's lockfile to
`manifests/<tag>.lock` so each tag's exact contents stay auditable from the repo.
Diff two releases with:

```bash
diff manifests/v2026.06.22.lock manifests/v2026.06.30.lock
```

## Integrity & signing

Each GitHub release publishes:

- `<iso>.sha256` — checksum of the reassembled ISO.
- `SHA256SUMS` — one manifest covering every split part **and** the provenance
  files.
- `SHA256SUMS.asc` / `<iso>.sha256.asc` — detached GPG signatures, **when a
  project signing key is configured** (`GPG_PRIVATE_KEY` / `GPG_PASSPHRASE`
  secrets; see [RELEASING.md](../RELEASING.md)). Releases are otherwise
  published unsigned.

## Verifying a download

Download the release files into one folder and run:

```bash
tools/verify-release.sh /path/to/download-dir      # or just: cd there && verify-release.sh
```

It checks the `SHA256SUMS` manifest, verifies the GPG signature (when present
and the public key is imported), reassembles the split ISO, and verifies the
whole-image checksum — checking only the files you actually downloaded, and
exiting non-zero if anything fails to match.
