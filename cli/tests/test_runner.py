import unittest

from arsenal_cli import runner


class TestRunner(unittest.TestCase):
    def test_echo_ok(self):
        r = runner.run(["echo", "hello"])
        self.assertTrue(r.ok)
        self.assertEqual(r.returncode, 0)
        self.assertIn("hello", r.stdout)

    def test_missing_command(self):
        r = runner.run(["arsenal-nonexistent-xyz"])
        self.assertTrue(r.missing)
        self.assertFalse(r.ok)
        self.assertEqual(r.returncode, 127)

    def test_failing_command(self):
        r = runner.run(["false"])
        self.assertFalse(r.ok)
        self.assertEqual(r.returncode, 1)

    def test_timeout(self):
        r = runner.run(["sleep", "5"], timeout=0.2)
        self.assertTrue(r.timed_out)
        self.assertFalse(r.ok)

    def test_which(self):
        self.assertIsNotNone(runner.which("echo"))
        self.assertIsNone(runner.which("arsenal-nonexistent-xyz"))


if __name__ == "__main__":
    unittest.main()
