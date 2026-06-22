import io
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from arsenal_cli import config, runner, ui
from arsenal_cli.commands import dashboard, doctor
from arsenal_cli.project import Project, Step


def _checks():
    return [
        doctor.Check("Hardened kernel active", ui.Status.OK, "x-hardened"),
        doctor.Check("Firewall", ui.Status.FAIL, "inactive"),
        doctor.Check("Arsenal version", ui.Status.INFO, "rolling"),
    ]


class TestDashboard(unittest.TestCase):
    def setUp(self):
        ui.set_color(False)

    def test_render_html_contains_status_and_version(self):
        data = {
            "version": "2026.06.21",
            "checks": _checks(),
            "weapons": (5, 20),
            "recent": [],
            "generated": "now",
        }
        html = dashboard._render_html(data)
        self.assertIn("Arsenal Dashboard", html)
        self.assertIn("2026.06.21", html)
        self.assertIn("5/20", html)
        self.assertIn("Hardened kernel active", html)

    def test_weapons_counts(self):
        with tempfile.TemporaryDirectory() as td:
            reg = Path(td) / "registry"
            reg.write_text("sniper|nmap|Recon|x\nbazooka|msfconsole|Exploit|y\n")
            with mock.patch.object(config, "REGISTRY", reg), \
                 mock.patch.object(runner, "which", side_effect=lambda b: "/p" if b == "nmap" else None):
                inst, total = dashboard._weapons()
        self.assertEqual((inst, total), (1, 2))

    def test_recent_reads_projects(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            p = Project.create("eng1", kind="recon", target="t", base=base)
            p.add_step(Step("nmap", status="ok"))
            with mock.patch.object(config, "ENGAGEMENTS_DIR", base):
                recent = dashboard._recent()
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["name"], "eng1")

    def test_run_tui(self):
        with mock.patch.object(dashboard.doctor, "gather", return_value=_checks()), \
             mock.patch.object(dashboard, "_weapons", return_value=(5, 20)), \
             mock.patch.object(dashboard, "_recent", return_value=[]):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = dashboard.run(types.SimpleNamespace(tui=True, no_open=False, output=None))
        self.assertEqual(rc, 0)
        self.assertIn("Arsenal Dashboard", buf.getvalue())

    def test_run_html_no_open(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "dash.html"
            with mock.patch.object(dashboard.doctor, "gather", return_value=_checks()), \
                 mock.patch.object(dashboard, "_weapons", return_value=(1, 2)), \
                 mock.patch.object(dashboard, "_recent", return_value=[]), \
                 mock.patch.object(runner, "run") as run_mock:
                with redirect_stdout(io.StringIO()):
                    rc = dashboard.run(types.SimpleNamespace(tui=False, no_open=True, output=str(out)))
            self.assertEqual(rc, 0)
            self.assertTrue(out.is_file())
            run_mock.assert_not_called()  # --no-open => no xdg-open


if __name__ == "__main__":
    unittest.main()
