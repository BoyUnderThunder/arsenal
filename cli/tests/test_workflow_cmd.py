"""Tests for the CLI command layer (commands/workflow.py) — the authorization
gate and arg wiring, distinct from the workflow engine (test_workflows.py)."""
import io
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from arsenal_cli import ui
from arsenal_cli.commands import workflow


def _args(**kw):
    base = {"target": "example.com", "wordlist": None, "yes": False, "dry_run": False,
            "name": None, "output": None, "user": None, "password": None, "dc_ip": None}
    base.update(kw)
    return types.SimpleNamespace(**base)


class TestAuthGate(unittest.TestCase):
    def setUp(self):
        ui.set_color(False)

    def test_yes_authorizes(self):
        self.assertTrue(workflow._authorized("target", True))

    def test_non_tty_refuses_without_yes(self):
        with mock.patch.object(workflow.sys.stdin, "isatty", return_value=False), \
             redirect_stderr(io.StringIO()):
            self.assertFalse(workflow._authorized("target", False))

    def test_interactive_yes(self):
        with mock.patch.object(workflow.sys.stdin, "isatty", return_value=True), \
             mock.patch("builtins.input", return_value="y"), redirect_stdout(io.StringIO()):
            self.assertTrue(workflow._authorized("target", False))


class TestDispatch(unittest.TestCase):
    def setUp(self):
        ui.set_color(False)

    def test_recon_dry_run_returns_0(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(workflow.recon(_args(dry_run=True)), 0)

    def test_recon_refused_without_authorization(self):
        with mock.patch.object(workflow, "_authorized", return_value=False):
            self.assertEqual(workflow.recon(_args()), 2)

    def test_web_and_ad_refused_without_authorization(self):
        with mock.patch.object(workflow, "_authorized", return_value=False):
            self.assertEqual(workflow.web(_args()), 2)
            self.assertEqual(workflow.ad(_args()), 2)

    def test_ad_passes_credentials_through(self):
        captured = {}

        class FakeWF:
            def __init__(self, target, **kw):
                captured["target"] = target
                captured["extra"] = kw.get("extra")

            def run(self):
                return 0

        with mock.patch.object(workflow, "_authorized", return_value=True), \
             mock.patch.object(workflow, "ADWorkflow", FakeWF):
            rc = workflow.ad(_args(user="u", password="p", dc_ip="10.0.0.1"))
        self.assertEqual(rc, 0)
        self.assertEqual(captured["extra"], {"user": "u", "password": "p", "dc_ip": "10.0.0.1"})


if __name__ == "__main__":
    unittest.main()
