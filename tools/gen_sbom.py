#!/usr/bin/env python3
"""Generate Arsenal supply-chain provenance from a package list.

Reads ``pacman -Q`` output (one ``name version`` per line) on stdin and writes:

* a **lockfile** — sorted ``name version`` lines, the exact contents of the
  image, suitable for committing as ``manifests/<tag>.lock`` and diffing
  between builds; and
* a **CycloneDX 1.5 SBOM** (JSON) listing every package as a component with an
  Arch Linux ``pkg:alpm`` PURL.

Kept dependency-free (stdlib only) so it runs in the build container as-is.

Usage:
    pacman -Q --dbpath <airootfs>/var/lib/pacman \
        | tools/gen_sbom.py --os-name arsenal --os-version 2026.06.27 \
              --arch x86_64 --snapshot 2026/06/23 \
              --lock out/arsenal.iso.lock --sbom out/arsenal.iso.cdx.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
import uuid


def parse_packages(stream) -> list[tuple[str, str]]:
    """Parse ``name version`` lines into a sorted, de-duplicated list."""
    pkgs: dict[str, str] = {}
    for raw in stream:
        line = raw.strip()
        if not line:
            continue
        name, _, version = line.partition(" ")
        if not name or not version:
            continue  # skip malformed lines rather than emit junk
        pkgs[name] = version.strip()
    return sorted(pkgs.items())


def build_sbom(pkgs, os_name, os_version, arch, snapshot):
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Deterministic serial from the package set + identity, so identical inputs
    # yield an identical (timestamp aside) document.
    digest = hashlib.sha256(
        ("\n".join(f"{n} {v}" for n, v in pkgs) + f"|{os_name}|{os_version}|{arch}").encode()
    ).hexdigest()
    serial = "urn:uuid:" + str(uuid.UUID(digest[:32]))

    props = [{"name": "arsenal:package_count", "value": str(len(pkgs))}]
    if snapshot:
        props.append({"name": "arsenal:arch_snapshot", "value": snapshot})

    components = [
        {
            "type": "library",
            "name": name,
            "version": version,
            "purl": f"pkg:alpm/arch/{name}@{version}?arch={arch}",
        }
        for name, version in pkgs
    ]
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": serial,
        "version": 1,
        "metadata": {
            "timestamp": now,
            "tools": [{"vendor": "Arsenal", "name": "gen_sbom.py", "version": "1"}],
            "component": {
                "type": "operating-system",
                "name": os_name,
                "version": os_version,
                "description": "Arsenal — white-hat security OS (Arch + BlackArch)",
            },
            "properties": props,
        },
        "components": components,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--os-name", default="arsenal")
    ap.add_argument("--os-version", required=True)
    ap.add_argument("--arch", default="x86_64")
    ap.add_argument("--snapshot", default="", help="Arch Linux Archive snapshot date, for provenance")
    ap.add_argument("--lock", required=True, help="path to write the lockfile")
    ap.add_argument("--sbom", required=True, help="path to write the CycloneDX JSON SBOM")
    args = ap.parse_args(argv)

    pkgs = parse_packages(sys.stdin)
    if not pkgs:
        print("gen_sbom: no packages on stdin", file=sys.stderr)
        return 2

    header = (
        f"# Arsenal package lockfile — {args.os_name} {args.os_version} ({args.arch})\n"
        f"# {len(pkgs)} packages"
        + (f"; Arch snapshot {args.snapshot}\n" if args.snapshot else "\n")
    )
    with open(args.lock, "w", encoding="utf-8") as fh:
        fh.write(header)
        for name, version in pkgs:
            fh.write(f"{name} {version}\n")

    with open(args.sbom, "w", encoding="utf-8") as fh:
        json.dump(build_sbom(pkgs, args.os_name, args.os_version, args.arch, args.snapshot), fh, indent=2)
        fh.write("\n")

    print(f"gen_sbom: wrote {args.lock} and {args.sbom} ({len(pkgs)} packages)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
