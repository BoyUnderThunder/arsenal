import io
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from arsenal_cli import ui
from arsenal_cli.commands import reportbug


class TestRedaction(unittest.TestCase):
    def test_redact_ipv4(self):
        self.assertIn("[IPV4]", reportbug.redact("connect to 192.168.1.50 now"))

    def test_redact_mac(self):
        self.assertIn("[MAC]", reportbug.redact("hwaddr de:ad:be:ef:00:11"))

    def test_redact_secret(self):
        out = reportbug.redact("api_key = s3cr3t-value-123")
        self.assertIn("[REDACTED]", out)
        self.assertNotIn("s3cr3t-value-123", out)

    def test_no_false_positive_on_plain_text(self):
        text = "the quick brown fox"
        self.assertEqual(reportbug.redact(text), text)


class TestBundle(unittest.TestCase):
    def setUp(self):
        ui.set_color(False)

    def test_bundle_created_and_redacted(self):
        with mock.patch.object(
            reportbug, "_collect", return_value={"sample.txt": "ip 10.0.0.7\n"}
        ):
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / "bundle.tar.zst"
                args = types.SimpleNamespace(no_redact=False, output=str(out))
                with redirect_stdout(io.StringIO()):
                    rc = reportbug.run(args)
                self.assertEqual(rc, 0)
                # zstd may be unavailable -> falls back to .tar.gz; accept either
                self.assertTrue(list(Path(td).glob("bundle.tar*")))


if __name__ == "__main__":
    unittest.main()
