import io
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest import mock

from arsenal_cli import __main__ as cli


class TestDispatch(unittest.TestCase):
    def test_version_exits_zero(self):
        with self.assertRaises(SystemExit) as cm:
            with redirect_stdout(io.StringIO()):
                cli.main(["--version"])
        self.assertEqual(cm.exception.code, 0)

    def test_unknown_command_errors(self):
        with self.assertRaises(SystemExit):
            with redirect_stderr(io.StringIO()):
                cli.main(["definitely-not-a-command"])

    def test_default_is_armory(self):
        called = {}

        def fake(_args):
            called["armory"] = True
            return 0

        with mock.patch.dict(cli._COMMANDS, {"armory": (fake, "x")}):
            rc = cli.main([])
        self.assertTrue(called.get("armory"))
        self.assertEqual(rc, 0)

    def test_doctor_dispatch(self):
        with mock.patch.dict(cli._COMMANDS, {"doctor": (lambda a: 0, "x")}):
            with redirect_stdout(io.StringIO()):
                rc = cli.main(["doctor"])
        self.assertEqual(rc, 0)

    def test_handler_exception_returns_one(self):
        def boom(_args):
            raise RuntimeError("nope")

        with mock.patch.dict(cli._COMMANDS, {"armory": (boom, "x")}):
            with redirect_stderr(io.StringIO()):
                rc = cli.main([])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
