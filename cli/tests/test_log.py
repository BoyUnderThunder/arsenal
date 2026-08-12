import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from arsenal_cli import log


class TestLog(unittest.TestCase):
    def test_writable_log_dir_uses_env(self):
        with tempfile.TemporaryDirectory() as td, \
             mock.patch.dict(os.environ, {"ARSENAL_LOG_DIR": td}):
            self.assertEqual(log._writable_log_dir(), Path(td))

    def test_writable_log_dir_falls_back_to_tmp(self):
        # Every candidate directory is unwritable -> the /tmp fallback.
        with mock.patch.dict(os.environ, {"ARSENAL_LOG_DIR": ""}), \
             mock.patch.object(log.Path, "mkdir", side_effect=OSError):
            self.assertEqual(log._writable_log_dir(), Path("/tmp"))

    def test_get_logger_is_namespaced(self):
        self.assertEqual(log.get_logger("arsenal_cli.commands.doctor").name, "arsenal.doctor")

    def test_setup_is_idempotent(self):
        log._CONFIGURED = False
        root = logging.getLogger("arsenal")
        root.handlers.clear()
        try:
            log.setup()
            n = len(root.handlers)
            log.setup()  # second call must be a no-op
            self.assertEqual(len(root.handlers), n)
        finally:
            root.handlers.clear()
            log._CONFIGURED = False


if __name__ == "__main__":
    unittest.main()
