"""Unit tests for gen_sbom.py (Arsenal supply-chain provenance generator).

Run from this directory:  python -m unittest test_gen_sbom -v
"""
import io
import json
import os
import tempfile
import unittest

import gen_sbom


class TestParsePackages(unittest.TestCase):
    def test_sorts_and_dedups(self):
        pkgs = gen_sbom.parse_packages(io.StringIO("b 2\na 1\nb 2\n"))
        self.assertEqual(pkgs, [("a", "1"), ("b", "2")])

    def test_skips_malformed_and_blank_lines(self):
        pkgs = gen_sbom.parse_packages(io.StringIO("good 1.0\nnoversion\n\n   \n"))
        self.assertEqual(pkgs, [("good", "1.0")])

    def test_preserves_epoch_versions(self):
        pkgs = gen_sbom.parse_packages(io.StringIO("nftables 1:1.1.5-1\n"))
        self.assertEqual(pkgs, [("nftables", "1:1.1.5-1")])

    def test_last_version_wins_on_duplicate_name(self):
        pkgs = gen_sbom.parse_packages(io.StringIO("a 1\na 2\n"))
        self.assertEqual(pkgs, [("a", "2")])


class TestCycloneDX(unittest.TestCase):
    def _doc(self, pkgs, snapshot="2026/06/23"):
        return gen_sbom.build_sbom(pkgs, "arsenal", "2026.06.28", "x86_64", snapshot)

    def test_shape_and_purl(self):
        d = self._doc([("bash", "5.3-1")])
        self.assertEqual(d["bomFormat"], "CycloneDX")
        self.assertEqual(d["specVersion"], "1.5")
        self.assertTrue(d["serialNumber"].startswith("urn:uuid:"))
        self.assertEqual(d["metadata"]["component"]["type"], "operating-system")
        self.assertEqual(len(d["components"]), 1)
        self.assertEqual(d["components"][0]["purl"], "pkg:alpm/arch/bash@5.3-1?arch=x86_64")

    def test_properties_record_count_and_snapshot(self):
        d = self._doc([("bash", "5.3-1"), ("nmap", "7.99-1")])
        props = {p["name"]: p["value"] for p in d["metadata"]["properties"]}
        self.assertEqual(props["arsenal:package_count"], "2")
        self.assertEqual(props["arsenal:arch_snapshot"], "2026/06/23")

    def test_snapshot_omitted_when_empty(self):
        d = self._doc([("bash", "5.3-1")], snapshot="")
        names = {p["name"] for p in d["metadata"]["properties"]}
        self.assertNotIn("arsenal:arch_snapshot", names)

    def test_serial_is_deterministic_for_same_input(self):
        a = self._doc([("bash", "5.3-1"), ("nmap", "7.99-1")])
        b = self._doc([("bash", "5.3-1"), ("nmap", "7.99-1")])
        self.assertEqual(a["serialNumber"], b["serialNumber"])


class TestSPDX(unittest.TestCase):
    def _doc(self, pkgs, snapshot="2026/06/23"):
        return gen_sbom.build_spdx(pkgs, "arsenal", "2026.06.28", "x86_64", snapshot)

    def test_shape(self):
        d = self._doc([("gcc-libs", "14-1")])
        self.assertEqual(d["spdxVersion"], "SPDX-2.3")
        self.assertEqual(d["dataLicense"], "CC0-1.0")
        self.assertEqual(d["SPDXID"], "SPDXRef-DOCUMENT")
        self.assertTrue(d["documentNamespace"].startswith("https://"))
        self.assertIn("2026/06/23", d["creationInfo"]["comment"])

    def test_spdxids_valid_and_unique_even_after_sanitising(self):
        # Two distinct names that collapse to the same sanitised form must still
        # produce distinct, charset-valid SPDXIDs (disambiguated by index).
        d = self._doc([("lib+x", "1"), ("lib-x", "2")])
        ids = [p["SPDXID"] for p in d["packages"]]
        for i in ids:
            self.assertRegex(i, r"^SPDXRef-[A-Za-z0-9.\-]+$")
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(d["documentDescribes"], ids)

    def test_package_has_purl_external_ref(self):
        d = self._doc([("bash", "5.3-1")])
        ref = d["packages"][0]["externalRefs"][0]
        self.assertEqual(ref["referenceType"], "purl")
        self.assertEqual(ref["referenceLocator"], "pkg:alpm/arch/bash@5.3-1?arch=x86_64")


class TestMainIO(unittest.TestCase):
    def test_writes_lockfile_and_both_sboms(self):
        with tempfile.TemporaryDirectory() as d:
            lock = os.path.join(d, "x.lock")
            cdx = os.path.join(d, "x.cdx.json")
            spdx = os.path.join(d, "x.spdx.json")
            stdin = io.StringIO("bash 5.3-1\nnftables 1:1.1.5-1\n")
            rc = gen_sbom.main(
                ["--os-version", "2026.06.28", "--snapshot", "2026/06/23",
                 "--lock", lock, "--sbom", cdx, "--spdx", spdx],
                stdin=stdin,
            )
            self.assertEqual(rc, 0)
            with open(lock, encoding="utf-8") as fh:
                body = fh.read()
            self.assertIn("bash 5.3-1", body)
            self.assertIn("nftables 1:1.1.5-1", body)
            # lockfile is sorted (bash before nftables) after a comment header
            lines = [ln for ln in body.splitlines() if not ln.startswith("#")]
            self.assertEqual(lines, ["bash 5.3-1", "nftables 1:1.1.5-1"])
            with open(cdx, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["specVersion"], "1.5")
            with open(spdx, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["spdxVersion"], "SPDX-2.3")

    def test_spdx_is_optional(self):
        with tempfile.TemporaryDirectory() as d:
            lock = os.path.join(d, "x.lock")
            cdx = os.path.join(d, "x.cdx.json")
            rc = gen_sbom.main(
                ["--os-version", "1", "--lock", lock, "--sbom", cdx],
                stdin=io.StringIO("bash 5.3-1\n"),
            )
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.exists(os.path.join(d, "x.spdx.json")))

    def test_empty_input_returns_2(self):
        with tempfile.TemporaryDirectory() as d:
            rc = gen_sbom.main(
                ["--os-version", "1",
                 "--lock", os.path.join(d, "x.lock"),
                 "--sbom", os.path.join(d, "x.cdx.json")],
                stdin=io.StringIO("   \n\n"),
            )
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
