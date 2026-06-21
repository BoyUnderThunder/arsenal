import unittest

from arsenal_cli import ui


class TestUI(unittest.TestCase):
    def setUp(self):
        ui.set_color(False)

    def test_style_plain_when_disabled(self):
        self.assertEqual(ui.style("x", ui.RED), "x")

    def test_style_colored_when_enabled(self):
        ui.set_color(True)
        try:
            out = ui.style("x", ui.RED)
            self.assertIn(ui.RED, out)
            self.assertIn(ui.RESET, out)
        finally:
            ui.set_color(False)

    def test_badge_symbols(self):
        self.assertEqual(ui.badge(ui.Status.OK), "[✓]")
        self.assertEqual(ui.badge(ui.Status.FAIL), "[✗]")
        self.assertEqual(ui.badge(ui.Status.WARN), "[!]")
        self.assertEqual(ui.badge(ui.Status.INFO), "[i]")

    def test_severity_ordering(self):
        self.assertGreater(ui.SEVERITY[ui.Status.FAIL], ui.SEVERITY[ui.Status.WARN])
        self.assertGreater(ui.SEVERITY[ui.Status.WARN], ui.SEVERITY[ui.Status.OK])
        self.assertEqual(ui.SEVERITY[ui.Status.INFO], ui.SEVERITY[ui.Status.OK])

    def test_line_includes_detail(self):
        self.assertIn("detail", ui.line(ui.Status.OK, "msg", "detail"))


if __name__ == "__main__":
    unittest.main()
