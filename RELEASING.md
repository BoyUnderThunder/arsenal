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
# download every *.iso.part*, the .sha256, and SHA256SUMS into one folder, then:
sha256sum -c SHA256SUMS                               # verifies the parts + provenance
# if SHA256SUMS.asc is attached, the release is signed — import the public key, then:
gpg --verify SHA256SUMS.asc SHA256SUMS                # must print: Good signature
cat arsenal-<tag>-x86_64.iso.part?? > arsenal-<tag>-x86_64.iso
sha256sum -c arsenal-<tag>-x86_64.iso.sha256          # must print: OK
sudo dd if=arsenal-<tag>-x86_64.iso of=/dev/sdX bs=4M status=progress oflag=sync
```
(or feed the reassembled `.iso` to Ventoy / Rufus / balenaEtcher). The package
lockfile (`*.lock`) and CycloneDX SBOM (`*.cdx.json`) are attached for auditing.

## Reproducibility & provenance

Every build emits supply-chain provenance next to the ISO, uploaded as the
**`arsenal-provenance`** artifact (see `build-iso.yml`):

- **Lockfile** `<iso>.lock` — exact name+version of every installed package
  (the full dependency closure, read from the built image's pacman DB), sorted
  for stable diffs between builds. Commit the released build's lockfile as
  `manifests/<tag>.lock` so a tag's exact contents are auditable.
- **SBOM** `<iso>.cdx.json` — a CycloneDX 1.5 bill of materials with a
  `pkg:alpm` PURL per package and the Arch Linux Archive snapshot date recorded
  in `metadata.properties`.

Builds pin the Arch repos to a dated ALA snapshot (`ARSENAL_ARCH_SNAPSHOT`,
default set in `build.sh`; override or set `off` to disable), so a rebuild from
the same commit resolves the same Arch package versions. BlackArch has no dated
archive and stays rolling.

Each release also publishes a **`SHA256SUMS`** manifest covering every part and
provenance file, plus the lockfile and SBOM as release assets.

**Signing** is wired into `release.yml` but inert until a project key is
configured. To activate it:
1. Add repository secrets `GPG_PRIVATE_KEY` (an ASCII-armored private key) and
   `GPG_PASSPHRASE`.
2. Publish the corresponding **public** key (in the repo and/or release notes)
   so downloaders can import it for verification.

With the secret present, every release gains a detached, armored
`SHA256SUMS.asc` (and `<iso>.sha256.asc`); without it, releases publish unsigned
exactly as before. Signed git tags remain a manual step (`git tag -s <tag>`).

## Notes
- Build artifacts (`work/`, `out/`, `*.iso`) are gitignored; never commit them.
- A release tag is a snapshot. Fixes land on `main` and ship in the next tag.
- Current published release: **v2026.06.22**.
