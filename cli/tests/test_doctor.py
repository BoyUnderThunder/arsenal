import io
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from arsenal_cli import runner, ui
from arsenal_cli.commands import doctor


def _result(stdout="", rc=0):
    return runner.Result(["x"], rc, stdout, "", rc == 0)


class TestDoctorChecks(unittest.TestCase):
    def setUp(self):
        ui.set_color(False)

    def test_kernel_hardened(self):
        fake = types.SimpleNamespace(release="6.12.1-hardened1-1-hardened")
        with mock.patch.object(doctor.os, "uname", return_value=fake):
            self.assertEqual(doctor.check_kernel().status, ui.Status.OK)

    def test_kernel_stock(self):
        fake = types.SimpleNamespace(release="6.12.1-arch1-1")
        with mock.patch.object(doctor.os, "uname", return_value=fake):
            self.assertEqual(doctor.check_kernel().status, ui.Status.FAIL)

    def test_firewall_active_with_default_deny(self):
        def fake_run(cmd, **kw):
            if cmd[:2] == ["systemctl", "is-active"]:
                return _result("active\n")
            if cmd[0] == "nft":
                return _result("chain input { type filter hook input priority filter; policy drop; }")
            return _result()

        with mock.patch.object(doctor.runner, "run", side_effect=fake_run):
            self.assertEqual(doctor.check_firewall().status, ui.Status.OK)

    def test_firewall_active_without_default_deny(self):
        def fake_run(cmd, **kw):
            if cmd[:2] == ["systemctl", "is-active"]:
                return _result("active\n")
            return _result("chain input { policy accept; }")

        with mock.patch.object(doctor.runner, "run", side_effect=fake_run):
            self.assertEqual(doctor.check_firewall().status, ui.Status.WARN)

    def test_firewall_inactive(self):
        def fake_run(cmd, **kw):
            if cmd[:2] == ["systemctl", "is-active"]:
                return _result("inactive\n", rc=3)
            return _result()

        with mock.patch.object(doctor.runner, "run", side_effect=fake_run):
            self.assertEqual(doctor.check_firewall().status, ui.Status.FAIL)

    def test_firewall_inactive_service_but_rules_loaded(self):
        # Live ISO: nftables.service is a oneshot that exits after loading rules,
        # so it reads "inactive" while the default-deny ruleset is up. The loaded
        # ruleset is the ground truth, so this must be OK, not FAIL.
        def fake_run(cmd, **kw):
            if cmd[:2] == ["systemctl", "is-active"]:
                return _result("inactive\n", rc=3)
            if cmd[0] == "nft":
                return _result("chain input { type filter hook input priority filter; policy drop; }")
            return _result()

        with mock.patch.object(doctor.runner, "run", side_effect=fake_run):
            self.assertEqual(doctor.check_firewall().status, ui.Status.OK)

    def test_updates_available(self):
        with mock.patch.object(doctor.runner, "which", return_value="/usr/bin/checkupdates"):
            with mock.patch.object(doctor.runner, "run", return_value=_result("pkg1 1->2\npkg2 3->4\n")):
                c = doctor.check_updates()
        self.assertEqual(c.status, ui.Status.WARN)
        self.assertIn("2", c.detail)

    def test_disk_real(self):
        self.assertIn(doctor.check_disk().status, (ui.Status.OK, ui.Status.WARN, ui.Status.FAIL))

    def test_gather_isolates_exceptions(self):
        def boom():
            raise RuntimeError("kaboom")

        with mock.patch.object(doctor, "CHECKS", [boom]):
            results = doctor.gather()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, ui.Status.INFO)

    def test_run_smoke(self):
        ui.set_color(False)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            rc = doctor.run(None)
        self.assertIn(rc, (0, 1))


if __name__ == "__main__":
    unittest.main()
