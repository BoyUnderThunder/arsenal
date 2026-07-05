# Release lockfiles

Each public release records the exact package set that shipped in
`manifests/<tag>.lock` — one `name version` line per installed package (the full
dependency closure read from the built image's pacman DB), sorted for stable
diffs between releases.

These files are written automatically by `release.yml` when a release is cut
(best-effort; the same lockfile is always attached to the GitHub Release as an
asset regardless). To diff two releases:

    diff manifests/v2026.06.22.lock manifests/v2026.06.27.lock

The matching CycloneDX (`*.cdx.json`) and SPDX (`*.spdx.json`) SBOMs are attached
to each release. Builds pin Arch to a dated Arch Linux Archive snapshot
(`ARSENAL_ARCH_SNAPSHOT` in `build.sh`), so a rebuild from the same commit
resolves the same Arch package versions. See `../RELEASING.md`.
