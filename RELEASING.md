# Releasing Arsenal

How a public Arsenal release is produced. Releases are cut from **`main`** so
the latest tag always builds from the source of truth.

## Pipeline overview

1. **`build-iso.yml`** builds the ISO (archiso + BlackArch) in a privileged
   `archlinux` container on a GitHub-hosted runner, boot-tests it in QEMU, and
   uploads it as the **`arsenal-iso`** artifact.
2. **`release.yml`** takes that artifact, splits it into <2 GiB parts (GitHub's
   per-asset cap), writes a checksum, and publishes a public GitHub Release.

## Version scheme

Calendar tags: `vYYYY.MM.DD` (e.g. `v2026.06.22`). Re-releases on the same day
get a letter suffix (`v2026.06.22a`).

## Step-by-step

### 1. Build from `main`
Push/merge to `main`, or run **Actions → build-arsenal-iso → Run workflow** on
`main` (choose `full` or `lean`). Wait for it to go **green** (build **and**
QEMU boot test). Note its **run ID** (in the run URL, or via the Actions API).

### 2. Publish the release
**Actions → release-arsenal → Run workflow**, with:
- `run_id` = the green build-iso run from step 1,
- `tag` = `vYYYY.MM.DD`.

`release.yml` (ref `main`) downloads the `arsenal-iso` artifact, runs
`split -b 1900M` to produce `*.iso.part00…partNN`, writes `*.iso.sha256`,
generates release notes, and `gh release create`s the tag pinned to `main`'s
commit (`--target ${{ github.sha }}`).

### 3. Verify
Open the release page and confirm all `*.iso.part*` plus the `.sha256` are
attached and the tag points at the `main` commit you built from.

## What users do with a release

```bash
# download every *.iso.part* and the .sha256 into one folder, then:
cat arsenal-<tag>-x86_64.iso.part?? > arsenal-<tag>-x86_64.iso
sha256sum -c arsenal-<tag>-x86_64.iso.sha256          # must print: OK
sudo dd if=arsenal-<tag>-x86_64.iso of=/dev/sdX bs=4M status=progress oflag=sync
```
(or feed the reassembled `.iso` to Ventoy / Rufus / balenaEtcher).

## Reproducibility & provenance (roadmap: Tier 1)

Planned additions, documented here as they land:
- **Per-release lockfile** `manifests/<tag>.lock` (exact name+version of every
  installed package) and an **SBOM** (CycloneDX/SPDX) release asset, with a
  documented rebuild path.
- **Signing:** a detached GPG signature for the ISO and each split part, a
  signed `SHA256SUMS.asc`, and signed git tags, with `gpg --verify` steps in the
  release notes. (Requires a project signing key in CI secrets —
  `GPG_PRIVATE_KEY` / `GPG_PASSPHRASE` — and the public key published for
  verification.)

## Notes
- Build artifacts (`work/`, `out/`, `*.iso`) are gitignored; never commit them.
- A release tag is a snapshot. Fixes land on `main` and ship in the next tag.
- Current published release: **v2026.06.22**.
