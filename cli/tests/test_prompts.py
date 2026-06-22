import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

from arsenal_cli import prompts, ui


class TestConfirmOrExit(unittest.TestCase):
    def setUp(self):
        ui.set_color(False)

    def test_assume_yes_proceeds(self):
        # --yes: no prompt, caller proceeds (None).
        self.assertIsNone(prompts.confirm_or_exit("Go?", assume_yes=True))

    def test_yes_proceeds(self):
        with mock.patch("builtins.input", return_value="Y"):
            self.assertIsNone(prompts.confirm_or_exit("Go?"))

    def test_no_returns_zero(self):
        with mock.patch("builtins.input", return_value="n"), redirect_stdout(io.StringIO()):
            self.assertEqual(prompts.confirm_or_exit("Go?"), 0)

    def test_eof_returns_one(self):
        with mock.patch("builtins.input", side_effect=EOFError), redirect_stdout(io.StringIO()):
            self.assertEqual(prompts.confirm_or_exit("Go?"), 1)


if __name__ == "__main__":
    unittest.main()
