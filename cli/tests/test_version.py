import configparser
import unittest
from unittest import mock

from arsenal_cli import version


def _cfg(**arsenal):
    cp = configparser.ConfigParser()
    cp.read_dict({"arsenal": {"version": "rolling", "build_date": "", **arsenal}})
    return cp


class TestVersion(unittest.TestCase):
    def test_uses_config_version_with_build_date(self):
        with mock.patch.object(version, "load",
                               return_value=_cfg(version="2026.07.12", build_date="2026.07.12")):
            out = version.os_version()
        self.assertIn("2026.07.12", out)

    def test_falls_back_to_rolling_when_no_os_release(self):
        with mock.patch.object(version, "load", return_value=_cfg(version="rolling")), \
             mock.patch.object(version.Path, "read_text", side_effect=OSError):
            self.assertEqual(version.os_version(), "rolling")

    def test_reads_os_release_build_id(self):
        with mock.patch.object(version, "load", return_value=_cfg(version="rolling")), \
             mock.patch.object(version.Path, "read_text",
                               return_value='NAME="Arsenal"\nBUILD_ID=2026.07.10\n'):
            self.assertEqual(version.os_version(), "2026.07.10")

    def test_cli_version_nonempty(self):
        self.assertTrue(version.cli_version())


if __name__ == "__main__":
    unittest.main()
