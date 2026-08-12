import io
import json
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from arsenal_cli import config, ui
from arsenal_cli.commands import armory

REGISTRY_SAMPLE = """\
# comment line
sniper|nmap|Recon|Network mapper
bazooka|msfconsole|Exploitation|Metasploit console

malformed line without enough fields
"""


class TestArmory(unittest.TestCase):
    def setUp(self):
        ui.set_color(False)

    def test_renders_registry(self):
        with tempfile.TemporaryDirectory() as td:
            reg = Path(td) / "registry"
            reg.write_text(REGISTRY_SAMPLE)
            with mock.patch.object(config, "REGISTRY", reg):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = armory.run(None)
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("sniper", out)
        self.assertIn("nmap", out)
        self.assertIn("bazooka", out)
        self.assertIn("2 weapons", out)  # malformed/comment lines ignored

    def test_missing_registry(self):
        with mock.patch.object(config, "REGISTRY", Path("/no/such/registry")):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = armory.run(None)
        self.assertEqual(rc, 1)

    def test_json_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            reg = Path(td) / "registry"
            reg.write_text(REGISTRY_SAMPLE)
            # nmap "installed", msfconsole not — exercises both installed states.
            def fake_which(binary):
                return "/usr/bin/nmap" if binary == "nmap" else None

            buf = io.StringIO()
            with mock.patch.object(config, "REGISTRY", reg), \
                 mock.patch.object(armory.runner, "which", side_effect=fake_which), \
                 redirect_stdout(buf):
                rc = armory.run(types.SimpleNamespace(json=True))
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())  # must be valid JSON, no banner
        self.assertEqual(payload["count"], 2)
        first = payload["weapons"][0]
        self.assertEqual(first["weapon"], "sniper")
        self.assertEqual(first["tool"], "nmap")
        self.assertEqual(first["category"], "Recon")
        self.assertTrue(first["installed"])
        self.assertFalse(payload["weapons"][1]["installed"])

    def test_json_missing_registry(self):
        with mock.patch.object(config, "REGISTRY", Path("/no/such/registry")):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = armory.run(types.SimpleNamespace(json=True))
        self.assertEqual(rc, 1)
        payload = json.loads(buf.getvalue())  # error path still emits valid JSON
        self.assertEqual(payload["count"], 0)
        self.assertIn("error", payload)

    def _run(self, sample, **ns):
        with tempfile.TemporaryDirectory() as td:
            reg = Path(td) / "registry"
            reg.write_text(sample)
            buf = io.StringIO()
            with mock.patch.object(config, "REGISTRY", reg), redirect_stdout(buf):
                rc = armory.run(types.SimpleNamespace(**ns))
        return rc, buf.getvalue()

    def test_query_filters_table(self):
        # query matches on tool name (nmap) -> only sniper row, bazooka excluded.
        rc, out = self._run(REGISTRY_SAMPLE, json=False, query="nmap")
        self.assertEqual(rc, 0)
        self.assertIn("sniper", out)
        self.assertNotIn("bazooka", out)
        self.assertIn("1 weapon matching 'nmap'", out)

    def test_query_matches_category_case_insensitive(self):
        rc, out = self._run(REGISTRY_SAMPLE, json=False, query="EXPLOIT")
        self.assertIn("bazooka", out)
        self.assertNotIn("nmap", out)  # sniper's tool — unique to the filtered-out row

    def test_query_no_match(self):
        rc, out = self._run(REGISTRY_SAMPLE, json=False, query="zzz")
        self.assertEqual(rc, 0)
        self.assertIn("no weapons matching 'zzz'", out)

    def test_query_json_filters(self):
        rc, out = self._run(REGISTRY_SAMPLE, json=True, query="recon")
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["query"], "recon")
        self.assertEqual(payload["weapons"][0]["weapon"], "sniper")

    # nmap installed, msfconsole not — used by the presence-filter tests.
    @staticmethod
    def _which_nmap_only(binary):
        return "/usr/bin/nmap" if binary == "nmap" else None

    def test_installed_filter_table(self):
        with mock.patch.object(armory.runner, "which", side_effect=self._which_nmap_only):
            rc, out = self._run(REGISTRY_SAMPLE, json=False, installed=True)
        self.assertEqual(rc, 0)
        self.assertIn("sniper", out)          # nmap installed -> kept
        self.assertNotIn("msfconsole", out)   # bazooka missing -> dropped
        self.assertIn("1 weapon installed", out)

    def test_missing_filter_json(self):
        with mock.patch.object(armory.runner, "which", side_effect=self._which_nmap_only):
            rc, out = self._run(REGISTRY_SAMPLE, json=True, missing=True)
        payload = json.loads(out)
        self.assertEqual(payload["filter"], "missing")
        self.assertEqual([w["weapon"] for w in payload["weapons"]], ["bazooka"])

    def test_installed_plus_query_intersect(self):
        # bazooka matches 'exploit' by category but is NOT installed -> excluded.
        with mock.patch.object(armory.runner, "which", side_effect=self._which_nmap_only):
            rc, out = self._run(REGISTRY_SAMPLE, json=True, query="exploit", installed=True)
        payload = json.loads(out)
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["query"], "exploit")
        self.assertEqual(payload["filter"], "installed")


if __name__ == "__main__":
    unittest.main()
