import io
import os
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from unittest import mock

from arsenal_cli import runner, ui
from arsenal_cli.commands import update


def _res(stdout="", rc=0):
    return runner.Result(["pacman"], rc, stdout, "", rc == 0)


class TestUpdate(unittest.TestCase):
    def setUp(self):
        ui.set_color(False)

    def test_check_lists_pending(self):
        with mock.patch.object(runner, "which", return_value="/usr/bin/checkupdates"), \
             mock.patch.object(runner, "run", return_value=_res("pkg1 1->2\npkg2 2->3\n")):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = update.run(types.SimpleNamespace(check=True, yes=True, no_snapshot=True))
        self.assertEqual(rc, 0)
        self.assertIn("2 update", buf.getvalue())

    def test_update_requires_root(self):
        with mock.patch.object(update.os, "geteuid", return_value=1000), \
             mock.patch.object(runner, "which", return_value=None), \
             mock.patch.object(runner, "run", return_value=_res()):
            with redirect_stdout(io.StringIO()):
                rc = update.run(types.SimpleNamespace(check=False, yes=True, no_snapshot=True))
        self.assertEqual(rc, 1)

    def test_full_update_runs_keyrings_then_upgrade(self):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            return _res()

        with tempfile.TemporaryDirectory() as td:
            os.environ["ARSENAL_LOG_DIR"] = td
            try:
                with mock.patch.object(update.os, "geteuid", return_value=0), \
                     mock.patch.object(runner, "which", return_value="/usr/bin/x"), \
                     mock.patch.object(runner, "run", side_effect=fake_run):
                    with redirect_stdout(io.StringIO()):
                        rc = update.run(types.SimpleNamespace(check=False, yes=True, no_snapshot=True))
            finally:
                del os.environ["ARSENAL_LOG_DIR"]
        self.assertEqual(rc, 0)
        flat = [" ".join(c) for c in calls]
        self.assertTrue(any("archlinux-keyring" in c for c in flat))
        self.assertTrue(any("-Syu" in c for c in flat))


if __name__ == "__main__":
    unittest.main()
