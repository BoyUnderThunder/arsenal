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


if __name__ == "__main__":
    unittest.main()
