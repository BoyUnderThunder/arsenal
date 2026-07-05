"""Guard the arsenal(1) man page against drift.

The man page is hand-written troff, so it can silently fall behind the CLI.
This test pins it to the *real* subcommand set (imported from __main__) — add a
command without a man-page entry and CI fails — and checks the mandatory
sections are present.
"""
import re
import unittest
from pathlib import Path

from arsenal_cli.__main__ import _COMMANDS

MANPAGE = (
    Path(__file__).resolve().parents[2]
    / "profile" / "airootfs" / "usr" / "share" / "man" / "man1" / "arsenal.1"
)


class TestManpage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = MANPAGE.read_text()

    def test_manpage_exists(self):
        self.assertTrue(MANPAGE.is_file(), f"man page missing at {MANPAGE}")

    def test_has_mandatory_sections(self):
        self.assertRegex(self.text, r"(?m)^\.TH ARSENAL 1", "missing .TH header")
        for section in ("NAME", "SYNOPSIS", "DESCRIPTION", "COMMANDS"):
            self.assertRegex(self.text, rf"(?m)^\.SH {section}\b", f"missing .SH {section}")
        self.assertRegex(self.text, r"(?m)^\.SH NAME\narsenal \\-", "NAME line malformed")

    def test_every_subcommand_documented(self):
        for name in _COMMANDS:
            self.assertRegex(
                self.text,
                rf"(?m)^\.B {re.escape(name)}\b",
                f"subcommand '{name}' has no '.B {name}' entry in the man page",
            )

    def test_no_unknown_command_entries(self):
        # Every `.B <word>` command-style tag in COMMANDS should be a real
        # subcommand (guards against a renamed/removed command lingering).
        commands_block = self.text.split(".SH COMMANDS", 1)[-1].split(".SH FILES", 1)[0]
        tagged = set(re.findall(r"^\.B (\w[\w-]*)", commands_block, re.M))
        self.assertTrue(tagged, "no command entries found in COMMANDS section")
        self.assertEqual(tagged - set(_COMMANDS), set(), "man page documents unknown commands")


if __name__ == "__main__":
    unittest.main()
