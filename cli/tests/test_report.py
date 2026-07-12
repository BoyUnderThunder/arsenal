import io
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from arsenal_cli import ui
from arsenal_cli.commands import report as report_cmd
from arsenal_cli.project import Finding, Project, Step
from arsenal_cli.report import render_html, render_markdown, render_pdf


def _sample(base):
    p = Project.create("demo", kind="recon", target="example.com", base=base)
    p.add_step(Step(name="nmap", command="nmap -sV example.com", status="ok",
                    returncode=0, summary="22,80,443 open"))
    p.add_step(Step(name="ffuf", command="ffuf -u http://example.com/FUZZ", status="fail",
                    returncode=1, summary="wordlist missing <script>"))
    return p


class TestRenderers(unittest.TestCase):
    def test_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            md = render_markdown(_sample(Path(td)))
        self.assertIn("# Arsenal Report — demo", md)
        self.assertIn("nmap", md)
        self.assertIn("| Step | Status", md)

    def test_html_is_escaped_and_dark(self):
        with tempfile.TemporaryDirectory() as td:
            html = render_html(_sample(Path(td)))
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("--bg:#16181d", html)  # dark theme
        self.assertIn("&lt;script&gt;", html)  # the summary was HTML-escaped
        self.assertNotIn("<script>", html)

    def test_pdf_optional(self):
        with tempfile.TemporaryDirectory() as td:
            ok, msg = render_pdf(_sample(Path(td)), Path(td) / "r.pdf")
        if ok:
            self.assertTrue(Path(msg).exists())
        else:
            self.assertIn("WeasyPrint", msg)

    def test_findings_render_markdown_sorted_with_counts(self):
        with tempfile.TemporaryDirectory() as td:
            p = _sample(Path(td))
            p.add_finding(Finding("Info thing", severity="info", target="a"))
            p.add_finding(Finding("Critical RCE", severity="critical", target="b",
                                  refs=["CVE-2021-1"]))
            md = render_markdown(p)
        self.assertIn("## Findings", md)
        self.assertIn("2 finding(s)", md)
        self.assertIn("1 critical", md)
        # critical row must appear before the info row (most-severe first)
        self.assertLess(md.index("Critical RCE"), md.index("Info thing"))
        self.assertIn("CVE-2021-1", md)

    def test_findings_render_html_with_severity_class_and_escaped(self):
        with tempfile.TemporaryDirectory() as td:
            p = _sample(Path(td))
            p.add_finding(Finding("XSS <script>", severity="high", target="c"))
            html = render_html(p)
        self.assertIn("<h2>Findings</h2>", html)
        self.assertIn("sev-high", html)
        self.assertIn("&lt;script&gt;", html)  # finding title escaped
        self.assertNotIn("<script>", html)

    def test_no_findings_section_when_empty(self):
        with tempfile.TemporaryDirectory() as td:
            md = render_markdown(_sample(Path(td)))
        self.assertNotIn("## Findings", md)

    def test_scan_output_embedded_and_truncated(self):
        with tempfile.TemporaryDirectory() as td:
            p = Project.create("emb", kind="recon", base=Path(td))
            scan = p.scans_dir() / "nmap.txt"
            scan.write_text("22/tcp open ssh\n" + "\n".join(f"line{i}" for i in range(100)))
            p.add_step(Step(name="nmap", status="ok", summary="ok", output_file=str(scan)))
            md = render_markdown(p)
            html = render_html(p)
        self.assertIn("22/tcp open ssh", md)   # actual output embedded, not just a path
        self.assertIn("truncated", md)          # long file was truncated
        self.assertIn("<details>", html)
        self.assertIn("22/tcp open ssh", html)

    def test_missing_scan_file_is_tolerated(self):
        with tempfile.TemporaryDirectory() as td:
            p = Project.create("emb", base=Path(td))
            p.add_step(Step(name="x", status="ok", output_file="/no/such/file.txt"))
            md = render_markdown(p)  # must not raise on an unreadable output file
        self.assertIn("x", md)

    def test_markdown_cells_stay_single_line(self):
        with tempfile.TemporaryDirectory() as td:
            p = Project.create("nl", kind="recon", base=Path(td))
            p.add_step(Step(name="multi", status="ok",
                            summary="line one\nline two | with pipe"))
            md = render_markdown(p)
        rows = [ln for ln in md.splitlines() if ln.startswith("| multi")]
        self.assertEqual(len(rows), 1)  # newline did not split the row
        self.assertIn("line one line two / with pipe", rows[0])


class TestReportCommand(unittest.TestCase):
    def setUp(self):
        ui.set_color(False)

    def test_generates_md_and_html(self):
        with tempfile.TemporaryDirectory() as td:
            p = _sample(Path(td))
            outdir = Path(td) / "out"
            args = types.SimpleNamespace(project=str(p.path), format="all", output=str(outdir))
            with redirect_stdout(io.StringIO()):
                rc = report_cmd.run(args)
            self.assertEqual(rc, 0)
            self.assertTrue((outdir / "report.md").is_file())
            self.assertTrue((outdir / "report.html").is_file())

    def test_missing_project(self):
        with tempfile.TemporaryDirectory() as td:
            args = types.SimpleNamespace(project=td, format="md", output=None)
            with redirect_stdout(io.StringIO()):
                rc = report_cmd.run(args)
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
