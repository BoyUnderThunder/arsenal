"""Unit tests for verify-sbom.py (Arsenal SBOM validator).

Run from this directory:  python -m unittest test_verify_sbom -v
"""
import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

import gen_sbom

# verify-sbom.py has a hyphen, so it isn't importable by name — load it by path.
_spec = importlib.util.spec_from_file_location(
    "verify_sbom", os.path.join(os.path.dirname(__file__), "verify-sbom.py")
)
verify_sbom = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify_sbom)


PKGS = [("bash", "5.3-1"), ("nftables", "1:1.1.5-1"), ("nmap", "7.99-1")]


def _cdx(pkgs=PKGS, snapshot="2026/06/23"):
    return gen_sbom.build_sbom(pkgs, "arsenal", "2026.07.04", "x86_64", snapshot)


def _spdx(pkgs=PKGS, snapshot="2026/06/23"):
    return gen_sbom.build_spdx(pkgs, "arsenal", "2026.07.04", "x86_64", snapshot)


class TestValidateCycloneDX(unittest.TestCase):
    def test_generated_document_is_valid(self):
        # The producer and the validator must agree: a fresh gen_sbom document
        # has zero problems. This is the round-trip guarantee.
        self.assertEqual(verify_sbom.validate_cyclonedx(_cdx()), [])

    def test_rejects_non_object(self):
        self.assertTrue(verify_sbom.validate_cyclonedx([1, 2, 3]))

    def test_flags_bad_bomformat(self):
        d = _cdx()
        d["bomFormat"] = "SPDX"
        self.assertTrue(any("bomFormat" in p for p in verify_sbom.validate_cyclonedx(d)))

    def test_flags_empty_components(self):
        d = _cdx()
        d["components"] = []
        self.assertTrue(any("components" in p for p in verify_sbom.validate_cyclonedx(d)))

    def test_flags_purl_name_mismatch(self):
        d = _cdx()
        d["components"][0]["purl"] = "pkg:alpm/arch/evil@5.3-1?arch=x86_64"
        self.assertTrue(any("does not match" in p for p in verify_sbom.validate_cyclonedx(d)))

    def test_flags_malformed_purl(self):
        d = _cdx()
        d["components"][0]["purl"] = "not-a-purl"
        self.assertTrue(any("malformed purl" in p for p in verify_sbom.validate_cyclonedx(d)))

    def test_flags_mixed_architectures(self):
        d = _cdx()
        d["components"][0]["purl"] = "pkg:alpm/arch/bash@5.3-1?arch=aarch64"
        self.assertTrue(any("mix architectures" in p for p in verify_sbom.validate_cyclonedx(d)))

    def test_flags_package_count_mismatch(self):
        d = _cdx()
        for prop in d["metadata"]["properties"]:
            if prop["name"] == "arsenal:package_count":
                prop["value"] = "999"
        self.assertTrue(any("package_count" in p for p in verify_sbom.validate_cyclonedx(d)))

    def test_flags_root_not_operating_system(self):
        d = _cdx()
        d["metadata"]["component"]["type"] = "library"
        self.assertTrue(any("operating-system" in p for p in verify_sbom.validate_cyclonedx(d)))


class TestValidateSPDX(unittest.TestCase):
    def test_generated_document_is_valid(self):
        self.assertEqual(verify_sbom.validate_spdx(_spdx()), [])

    def test_flags_bad_version(self):
        d = _spdx()
        d["spdxVersion"] = "SPDX-9.9"
        self.assertTrue(any("spdxVersion" in p for p in verify_sbom.validate_spdx(d)))

    def test_flags_describes_mismatch(self):
        d = _spdx()
        d["documentDescribes"] = d["documentDescribes"][:-1]  # drop one
        self.assertTrue(any("documentDescribes" in p for p in verify_sbom.validate_spdx(d)))

    def test_flags_missing_purl_ref(self):
        d = _spdx()
        d["packages"][0]["externalRefs"] = []
        self.assertTrue(any("purl externalRef" in p for p in verify_sbom.validate_spdx(d)))


class TestCrossChecks(unittest.TestCase):
    def test_matching_cdx_and_spdx(self):
        self.assertEqual(
            verify_sbom._diff("x", verify_sbom._cdx_pkgs(_cdx()), verify_sbom._spdx_pkgs(_spdx()), "a", "b"),
            [],
        )

    def test_mismatched_sets_reported(self):
        problems = verify_sbom._diff(
            "cross-check",
            verify_sbom._cdx_pkgs(_cdx(PKGS)),
            verify_sbom._spdx_pkgs(_spdx(PKGS[:-1])),
            "CycloneDX",
            "SPDX",
        )
        self.assertTrue(problems)

    def test_parse_lock_ignores_header_and_blanks(self):
        text = "# header\n# 3 packages\nbash 5.3-1\n\nnmap 7.99-1\n"
        self.assertEqual(verify_sbom.parse_lock(text), {("bash", "5.3-1"), ("nmap", "7.99-1")})


class TestMainIO(unittest.TestCase):
    def _write(self, d, pkgs=PKGS):
        lock = os.path.join(d, "x.lock")
        cdx = os.path.join(d, "x.cdx.json")
        spdx = os.path.join(d, "x.spdx.json")
        stream = io.StringIO("".join(f"{n} {v}\n" for n, v in pkgs))
        gen_sbom.main(
            ["--os-version", "2026.07.04", "--snapshot", "2026/06/23",
             "--lock", lock, "--sbom", cdx, "--spdx", spdx],
            stdin=stream,
        )
        return lock, cdx, spdx

    def test_valid_bundle_passes(self):
        with tempfile.TemporaryDirectory() as d:
            lock, cdx, spdx = self._write(d)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = verify_sbom.main(["--sbom", cdx, "--spdx", spdx, "--lock", lock])
            self.assertEqual(rc, 0)
            self.assertIn("[PASS]", buf.getvalue())

    def test_corrupt_cdx_fails(self):
        with tempfile.TemporaryDirectory() as d:
            _lock, cdx, _spdx = self._write(d)
            with open(cdx, encoding="utf-8") as fh:
                doc = json.load(fh)
            doc["components"][0]["purl"] = "pkg:alpm/arch/tampered@0?arch=x86_64"
            with open(cdx, "w", encoding="utf-8") as fh:
                json.dump(doc, fh)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = verify_sbom.main(["--sbom", cdx])
            self.assertEqual(rc, 1)
            self.assertIn("[FAIL]", buf.getvalue())

    def test_lock_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as d:
            lock, cdx, _spdx = self._write(d)
            with open(lock, "a", encoding="utf-8") as fh:
                fh.write("extra-package 1.0\n")  # in lock, not in SBOM
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = verify_sbom.main(["--sbom", cdx, "--lock", lock])
            self.assertEqual(rc, 1)

    def test_missing_file_returns_2(self):
        rc = verify_sbom.main(["--sbom", "/no/such/sbom.json"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
