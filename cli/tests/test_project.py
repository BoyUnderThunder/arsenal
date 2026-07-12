import json
import tempfile
import unittest
from pathlib import Path

from arsenal_cli.project import Finding, Project, Step


class TestProject(unittest.TestCase):
    def test_create_layout_and_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            p = Project.create("Test Engagement!", kind="recon", target="10.0.0.0/24", base=Path(td))
            self.assertTrue(p.path.is_dir())
            for sub in ("scans", "loot", "logs", "report"):
                self.assertTrue((p.path / sub).is_dir())
            meta = json.loads((p.path / "arsenal.json").read_text())
            self.assertEqual(meta["kind"], "recon")
            self.assertEqual(meta["target"], "10.0.0.0/24")
            self.assertNotIn("path", meta)  # runtime-only field not serialized
            # name is slugified for the directory
            self.assertIn("Test-Engagement", p.path.name)

    def test_add_step_persists_and_reloads(self):
        with tempfile.TemporaryDirectory() as td:
            p = Project.create("eng", base=Path(td))
            p.add_step(Step(name="nmap", command="nmap -sV x", status="ok", returncode=0,
                            summary="3 ports"))
            reloaded = Project.load(p.path)
            self.assertEqual(len(reloaded.steps), 1)
            self.assertEqual(reloaded.steps[0].name, "nmap")
            self.assertEqual(reloaded.steps[0].status, "ok")

    def test_counts(self):
        p = Project(name="x")
        p.steps = [Step("a", status="ok"), Step("b", status="fail"), Step("c", status="ok")]
        self.assertEqual(p.counts()["ok"], 2)
        self.assertEqual(p.counts()["fail"], 1)

    def test_findings_persist_and_reload(self):
        with tempfile.TemporaryDirectory() as td:
            p = Project.create("eng", base=Path(td))
            p.add_finding(Finding(title="Open port 22", severity="info", target="10.0.0.1"))
            p.add_finding(Finding(title="Anon FTP", severity="high", target="10.0.0.1",
                                  refs=["CVE-1999-0497"]))
            reloaded = Project.load(p.path)
            self.assertEqual(len(reloaded.findings), 2)
            self.assertIsInstance(reloaded.findings[0], Finding)
            self.assertEqual(reloaded.findings[1].refs, ["CVE-1999-0497"])

    def test_finding_counts_and_sort(self):
        p = Project(name="x")
        p.findings = [
            Finding("a", severity="info"), Finding("b", severity="critical"),
            Finding("c", severity="info"), Finding("d", severity="medium"),
        ]
        fc = p.finding_counts()
        self.assertEqual(fc["info"], 2)
        self.assertEqual(fc["critical"], 1)
        self.assertEqual(fc["low"], 0)  # every severity present
        # most-severe first
        self.assertEqual([f.severity for f in p.findings_sorted()],
                         ["critical", "medium", "info", "info"])

    def test_load_old_project_without_findings(self):
        # A project saved before findings existed must still load (default []).
        with tempfile.TemporaryDirectory() as td:
            p = Project.create("eng", base=Path(td))
            data = json.loads((p.path / "arsenal.json").read_text())
            data.pop("findings", None)  # simulate an older on-disk format
            (p.path / "arsenal.json").write_text(json.dumps(data))
            reloaded = Project.load(p.path)
            self.assertEqual(reloaded.findings, [])


if __name__ == "__main__":
    unittest.main()
