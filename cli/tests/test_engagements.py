import io
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from arsenal_cli import config, ui
from arsenal_cli.commands import engagements
from arsenal_cli.project import Finding, Project, Step


class TestEngagements(unittest.TestCase):
    def setUp(self):
        ui.set_color(False)

    def _mkproj(self, base, name="eng", kind="recon", target="example.com"):
        p = Project.create(name, kind=kind, target=target, base=Path(base))
        p.add_step(Step(name="nmap", status="ok", summary="2 open"))
        p.add_finding(Finding("Open port 22", "info", target))
        return p

    def _run(self, **ns):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = engagements.run(types.SimpleNamespace(**ns))
        return rc, buf.getvalue()

    def test_list_empty(self):
        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(config, "ENGAGEMENTS_DIR", Path(td)):
            rc, out = self._run(action="list")
        self.assertEqual(rc, 0)
        self.assertIn("none yet", out)

    def test_list_shows_projects(self):
        with tempfile.TemporaryDirectory() as td:
            self._mkproj(td, name="alpha")
            with mock.patch.object(config, "ENGAGEMENTS_DIR", Path(td)):
                rc, out = self._run(action="list")
        self.assertEqual(rc, 0)
        self.assertIn("alpha", out)
        self.assertIn("1 finding", out)

    def test_show(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._mkproj(td)
            rc, out = self._run(action="show", project=str(p.path))
        self.assertEqual(rc, 0)
        self.assertIn("nmap", out)
        self.assertIn("Open port 22", out)

    def test_show_missing_returns_1(self):
        rc, _ = self._run(action="show", project="/no/such/dir")
        self.assertEqual(rc, 1)

    def test_delete_with_yes(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._mkproj(td)
            rc, _ = self._run(action="delete", project=str(p.path), yes=True)
            self.assertEqual(rc, 0)
            self.assertFalse(p.path.exists())  # checked before the tempdir is torn down

    def test_archive_creates_tarball(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._mkproj(td)
            out = Path(td) / "arch.tar.gz"
            rc, _ = self._run(action="archive", project=str(p.path), output=str(out))
            self.assertEqual(rc, 0)
            self.assertTrue(out.is_file())

    def test_rerun_authorizes_and_reconstructs(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._mkproj(td, kind="recon", target="example.com")
            with mock.patch("arsenal_cli.commands.workflow._authorized", return_value=True), \
                 mock.patch("arsenal_cli.workflows.recon.ReconWorkflow.run",
                            return_value=0) as run_mock:
                rc, _ = self._run(action="rerun", project=str(p.path), yes=True)
        self.assertEqual(rc, 0)
        run_mock.assert_called_once()

    def test_rerun_refused_without_authorization(self):
        with tempfile.TemporaryDirectory() as td:
            p = self._mkproj(td, kind="recon", target="example.com")
            with mock.patch("arsenal_cli.commands.workflow._authorized", return_value=False):
                rc, _ = self._run(action="rerun", project=str(p.path), yes=False)
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
