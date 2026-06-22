import io
import types
import unittest
from contextlib import redirect_stdout
from unittest import mock

from arsenal_cli import runner, ui
from arsenal_cli.commands import profile


class TestProfile(unittest.TestCase):
    def setUp(self):
        ui.set_color(False)

    def test_all_profiles_present(self):
        self.assertEqual(set(profile.available()), {"red", "blue", "forensics", "reverse"})

    def test_packages_parsed(self):
        pkgs = profile.packages("red")
        self.assertIn("seclists", pkgs)
        self.assertTrue(all(not p.startswith("#") for p in pkgs))
        self.assertTrue(pkgs)

    def test_list(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = profile.run(types.SimpleNamespace(name="list", show=False, yes=False))
        self.assertEqual(rc, 0)
        self.assertIn("red", buf.getvalue())
        self.assertIn("forensics", buf.getvalue())

    def test_unknown_profile(self):
        with redirect_stdout(io.StringIO()):
            rc = profile.run(types.SimpleNamespace(name="bogus", show=False, yes=False))
        self.assertEqual(rc, 1)

    def test_show_does_not_install(self):
        with mock.patch.object(runner, "run") as run_mock:
            with redirect_stdout(io.StringIO()):
                rc = profile.run(types.SimpleNamespace(name="blue", show=True, yes=False))
        self.assertEqual(rc, 0)
        run_mock.assert_not_called()

    def test_install_requires_root(self):
        with mock.patch.object(profile.os, "geteuid", return_value=1000):
            with mock.patch.object(runner, "run") as run_mock:
                with redirect_stdout(io.StringIO()):
                    rc = profile.run(types.SimpleNamespace(name="red", show=False, yes=True))
        self.assertEqual(rc, 1)
        run_mock.assert_not_called()

    def test_install_as_root_invokes_pacman(self):
        with mock.patch.object(profile.os, "geteuid", return_value=0):
            with mock.patch.object(runner, "run",
                                   return_value=runner.Result(["pacman"], 0, "", "", True)) as run_mock:
                with redirect_stdout(io.StringIO()):
                    rc = profile.run(types.SimpleNamespace(name="reverse", show=False, yes=True))
        self.assertEqual(rc, 0)
        # last call should be the install
        install_calls = [c for c in run_mock.call_args_list if "-S" in c.args[0]]
        self.assertTrue(install_calls)


if __name__ == "__main__":
    unittest.main()
