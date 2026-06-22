import io
import tempfile
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


if __name__ == "__main__":
    unittest.main()
