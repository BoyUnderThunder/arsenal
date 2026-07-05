#!/usr/bin/env python3
"""Validate Arsenal supply-chain provenance produced by ``gen_sbom.py``.

Closes the loop on the provenance tier: ``gen_sbom.py`` *writes* the CycloneDX
SBOM, the SPDX SBOM and the lockfile; this script *checks* they are well-formed
and mutually consistent, so a corrupt or truncated artifact fails loudly
instead of being trusted.

Checks, all stdlib-only:

* **CycloneDX** — ``bomFormat``/``specVersion``, a ``urn:uuid`` serial, an
  ``operating-system`` root component, a non-empty component list, and that
  every component's ``pkg:alpm`` PURL matches its own name/version and a single
  shared architecture. Any ``arsenal:package_count`` property must agree.
* **SPDX** (optional) — ``spdxVersion``/document SPDXID/namespace, unique
  well-formed package SPDXIDs each carrying a ``purl`` external ref, and a
  ``documentDescribes`` that covers exactly those packages.
* **Cross-checks** — the CycloneDX, SPDX and lockfile (any provided) must
  describe the *same* set of ``(name, version)`` pairs.

Usage:
    tools/verify-sbom.py --sbom out/arsenal.iso.cdx.json \
        [--spdx out/arsenal.iso.spdx.json] [--lock out/arsenal.iso.lock]

Exit: 0 valid · 1 validation problems found · 2 usage / I/O error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys


def _purl(name: str, version: str, arch: str) -> str:
    return f"pkg:alpm/arch/{name}@{version}?arch={arch}"


def validate_cyclonedx(doc) -> list[str]:
    """Return a list of problem strings (empty means the document is valid)."""
    if not isinstance(doc, dict):
        return ["CycloneDX: document is not a JSON object"]
    problems: list[str] = []
    if doc.get("bomFormat") != "CycloneDX":
        problems.append("CycloneDX: bomFormat is not 'CycloneDX'")
    if not re.fullmatch(r"\d+\.\d+", str(doc.get("specVersion", ""))):
        problems.append(f"CycloneDX: specVersion {doc.get('specVersion')!r} is not X.Y")
    serial = doc.get("serialNumber", "")
    if not isinstance(serial, str) or not serial.startswith("urn:uuid:"):
        problems.append("CycloneDX: serialNumber is not a urn:uuid")
    if not isinstance(doc.get("version"), int):
        problems.append("CycloneDX: version is not an integer")

    meta = doc.get("metadata") or {}
    root = meta.get("component") or {}
    if root.get("type") != "operating-system":
        problems.append("CycloneDX: metadata.component.type is not 'operating-system'")
    if not root.get("name") or not root.get("version"):
        problems.append("CycloneDX: metadata.component missing name/version")

    components = doc.get("components")
    if not isinstance(components, list) or not components:
        problems.append("CycloneDX: components is empty or not a list")
        return problems

    arches: set[str] = set()
    seen: set[tuple[str, str]] = set()
    for i, c in enumerate(components):
        name, version, purl = c.get("name"), c.get("version"), c.get("purl", "")
        where = f"component[{i}] {name or '?'}"
        if not name or not version:
            problems.append(f"CycloneDX: {where}: missing name/version")
            continue
        if (name, version) in seen:
            problems.append(f"CycloneDX: duplicate component {name} {version}")
        seen.add((name, version))
        m = re.search(r"\?arch=([^?&]+)$", purl)
        if not purl.startswith("pkg:alpm/arch/") or not m:
            problems.append(f"CycloneDX: {where}: malformed purl {purl!r}")
            continue
        arch = m.group(1)
        arches.add(arch)
        if purl != _purl(name, version, arch):
            problems.append(f"CycloneDX: {where}: purl {purl!r} does not match name/version")
    if len(arches) > 1:
        problems.append(f"CycloneDX: components mix architectures {sorted(arches)}")

    for prop in meta.get("properties") or []:
        if prop.get("name") == "arsenal:package_count":
            try:
                if int(prop.get("value")) != len(components):
                    problems.append("CycloneDX: arsenal:package_count != number of components")
            except (TypeError, ValueError):
                problems.append("CycloneDX: arsenal:package_count is not an integer")
    return problems


def validate_spdx(doc) -> list[str]:
    if not isinstance(doc, dict):
        return ["SPDX: document is not a JSON object"]
    problems: list[str] = []
    if not str(doc.get("spdxVersion", "")).startswith("SPDX-2."):
        problems.append(f"SPDX: spdxVersion {doc.get('spdxVersion')!r} is not SPDX-2.x")
    if doc.get("SPDXID") != "SPDXRef-DOCUMENT":
        problems.append("SPDX: SPDXID is not 'SPDXRef-DOCUMENT'")
    if not doc.get("documentNamespace"):
        problems.append("SPDX: missing documentNamespace")
    if not (doc.get("creationInfo") or {}).get("created"):
        problems.append("SPDX: missing creationInfo.created")

    packages = doc.get("packages")
    if not isinstance(packages, list) or not packages:
        problems.append("SPDX: packages is empty or not a list")
        return problems

    ids: set[str] = set()
    for i, p in enumerate(packages):
        name, ver, sid = p.get("name"), p.get("versionInfo"), p.get("SPDXID", "")
        where = f"package[{i}] {name or '?'}"
        if not name or not ver:
            problems.append(f"SPDX: {where}: missing name/versionInfo")
        if not re.fullmatch(r"SPDXRef-[A-Za-z0-9.\-]+", sid):
            problems.append(f"SPDX: {where}: invalid SPDXID {sid!r}")
        elif sid in ids:
            problems.append(f"SPDX: duplicate SPDXID {sid}")
        else:
            ids.add(sid)
        refs = p.get("externalRefs") or []
        if not any(r.get("referenceType") == "purl" for r in refs):
            problems.append(f"SPDX: {where}: no purl externalRef")

    describes = doc.get("documentDescribes")
    if not isinstance(describes, list) or set(describes) != ids:
        problems.append("SPDX: documentDescribes does not cover exactly the package SPDXIDs")
    return problems


def _cdx_pkgs(doc) -> set[tuple[str, str]]:
    return {(c.get("name"), c.get("version")) for c in doc.get("components", [])}


def _spdx_pkgs(doc) -> set[tuple[str, str]]:
    return {(p.get("name"), p.get("versionInfo")) for p in doc.get("packages", [])}


def parse_lock(text: str) -> set[tuple[str, str]]:
    pkgs: set[tuple[str, str]] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, _, version = line.partition(" ")
        if name and version.strip():
            pkgs.add((name, version.strip()))
    return pkgs


def _diff(label: str, a: set, b: set, a_name: str, b_name: str) -> list[str]:
    if a == b:
        return []
    problems = []
    only_a, only_b = a - b, b - a
    if only_a:
        problems.append(f"{label}: {len(only_a)} package(s) only in {a_name} (e.g. {sorted(only_a)[:3]})")
    if only_b:
        problems.append(f"{label}: {len(only_b)} package(s) only in {b_name} (e.g. {sorted(only_b)[:3]})")
    return problems


def _load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Validate Arsenal SBOM/provenance artifacts.")
    ap.add_argument("--sbom", required=True, help="CycloneDX JSON SBOM to validate")
    ap.add_argument("--spdx", default="", help="optional SPDX JSON SBOM to also validate + cross-check")
    ap.add_argument("--lock", default="", help="optional lockfile to cross-check the package set against")
    args = ap.parse_args(argv)

    try:
        cdx = _load_json(args.sbom)
    except (OSError, json.JSONDecodeError) as e:
        print(f"verify-sbom: cannot read CycloneDX SBOM {args.sbom}: {e}", file=sys.stderr)
        return 2

    problems = validate_cyclonedx(cdx)

    if args.spdx:
        try:
            spdx = _load_json(args.spdx)
        except (OSError, json.JSONDecodeError) as e:
            print(f"verify-sbom: cannot read SPDX SBOM {args.spdx}: {e}", file=sys.stderr)
            return 2
        problems += validate_spdx(spdx)
        problems += _diff("cross-check", _cdx_pkgs(cdx), _spdx_pkgs(spdx), "CycloneDX", "SPDX")

    if args.lock:
        try:
            with open(args.lock, encoding="utf-8") as fh:
                lock_text = fh.read()
        except OSError as e:
            print(f"verify-sbom: cannot read lockfile {args.lock}: {e}", file=sys.stderr)
            return 2
        problems += _diff("cross-check", _cdx_pkgs(cdx), parse_lock(lock_text), "CycloneDX", "lockfile")

    if problems:
        for p in problems:
            print(f"[FAIL] {p}")
        print(f"verify-sbom: {len(problems)} problem(s) found", file=sys.stderr)
        return 1

    print(f"[PASS] SBOM valid — {len(_cdx_pkgs(cdx))} packages, consistent across all provided artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
