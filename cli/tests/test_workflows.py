import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from arsenal_cli import runner, ui
from arsenal_cli.project import Project
from arsenal_cli.workflows import recon as recon_mod
from arsenal_cli.workflows.ad import ADWorkflow
from arsenal_cli.workflows.base import as_host, as_url
from arsenal_cli.workflows.recon import ReconWorkflow
from arsenal_cli.workflows.web import WebWorkflow


def ok_result(stdout="80/tcp open http\n"):
    return runner.Result(["x"], 0, stdout, "", True)


class TestPlans(unittest.TestCase):
    def test_recon_plan_with_wordlist(self):
        with mock.patch.object(recon_mod, "find_wordlist", return_value="/tmp/wl.txt"):
            names = [t.name for t in ReconWorkflow("example.com").plan()]
        self.assertEqual(names[0], "nmap")
        self.assertIn("gobuster", names)
        self.assertIn("ffuf", names)

    def test_recon_plan_without_wordlist(self):
        with mock.patch.object(recon_mod, "find_wordlist", return_value=None):
            tasks = ReconWorkflow("example.com").plan()
        disc = [t for t in tasks if t.name == "web-content-discovery"]
        self.assertTrue(disc and disc[0].argv == [])  # note-only step

    def test_web_plan(self):
        self.assertEqual([t.name for t in WebWorkflow("http://t").plan()],
                         ["nikto", "sqlmap", "burpsuite"])

    def test_ad_plan_no_creds(self):
        names = [t.name for t in ADWorkflow("corp.local").plan()]
        self.assertIn("netexec-smb", names)
        self.assertIn("credentialed-collection", names)

    def test_ad_plan_with_creds(self):
        names = [t.name for t in ADWorkflow("corp.local", extra={"user": "u", "password": "p"}).plan()]
        self.assertIn("bloodhound-python", names)

    def test_target_normalization(self):
        self.assertEqual(as_host("https://example.com/admin"), "example.com")
        self.assertEqual(as_host("10.0.0.1"), "10.0.0.1")
        self.assertEqual(as_url("example.com"), "http://example.com")
        self.assertEqual(as_url("https://x"), "https://x")


class TestRun(unittest.TestCase):
    def setUp(self):
        ui.set_color(False)

    def test_dry_run_prints_plan(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = ReconWorkflow("example.com", dry_run=True).run()
        self.assertEqual(rc, 0)
        self.assertIn("nmap", buf.getvalue())

    def test_run_records_steps_and_writes_report(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(runner, "which", return_value="/usr/bin/tool"), \
                 mock.patch.object(runner, "run", return_value=ok_result()), \
                 mock.patch.object(recon_mod, "find_wordlist", return_value=None):
                with redirect_stdout(io.StringIO()):
                    rc = ReconWorkflow("example.com", base=Path(td)).run()
            projects = list(Path(td).glob("recon-*"))
            self.assertEqual(len(projects), 1)
            proj = Project.load(projects[0])
            self.assertTrue(any(s.name == "nmap" and s.status == "ok" for s in proj.steps))
            self.assertTrue((projects[0] / "report" / "report.html").is_file())
            self.assertEqual(rc, 0)

    def test_run_skips_missing_tool(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(runner, "which", return_value=None), \
                 mock.patch.object(recon_mod, "find_wordlist", return_value=None):
                with redirect_stdout(io.StringIO()):
                    rc = ReconWorkflow("example.com", base=Path(td)).run()
            proj = Project.load(list(Path(td).glob("recon-*"))[0])
            self.assertTrue(any(s.name == "nmap" and s.status == "skipped" for s in proj.steps))
            self.assertEqual(rc, 0)  # skipped is not a failure


if __name__ == "__main__":
    unittest.main()
