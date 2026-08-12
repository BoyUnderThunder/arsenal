import tempfile
import unittest
from pathlib import Path
from unittest import mock

from arsenal_cli import config

_NO_USER = Path("/no/such/user/arsenal.conf")


class TestConfig(unittest.TestCase):
    def test_defaults_present(self):
        with mock.patch.object(config, "SYSTEM_CONF", _NO_USER), \
             mock.patch.object(config, "USER_CONF", _NO_USER):
            cp = config.load()
        self.assertEqual(cp.get("ai", "provider"), "ollama")
        self.assertEqual(cp.get("arsenal", "channel"), "rolling")

    def test_system_conf_overrides_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            conf = Path(td) / "arsenal.conf"
            conf.write_text("[ai]\nprovider = openai\n")
            with mock.patch.object(config, "SYSTEM_CONF", conf), \
                 mock.patch.object(config, "USER_CONF", _NO_USER):
                cp = config.load()
        self.assertEqual(cp.get("ai", "provider"), "openai")
        self.assertEqual(cp.get("ai", "model"), "llama3")  # untouched default remains

    def test_malformed_config_does_not_crash(self):
        with tempfile.TemporaryDirectory() as td:
            conf = Path(td) / "bad.conf"
            conf.write_text("this is not valid ini [[[")
            with mock.patch.object(config, "SYSTEM_CONF", conf), \
                 mock.patch.object(config, "USER_CONF", _NO_USER):
                cp = config.load()  # must not raise
        self.assertEqual(cp.get("arsenal", "channel"), "rolling")  # defaults intact


if __name__ == "__main__":
    unittest.main()
