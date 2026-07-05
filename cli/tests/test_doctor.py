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

    def test_hardening_sysctls_all_applied(self):
        def fake_run(cmd, **kw):
            return _result(doctor._HARDENING_SYSCTLS[cmd[-1]] + "\n")

        with mock.patch.object(doctor.runner, "run", side_effect=fake_run):
            self.assertEqual(doctor.check_hardening_sysctls().status, ui.Status.OK)

    def test_hardening_sysctls_drift_warns(self):
        def fake_run(cmd, **kw):
            key = cmd[-1]
            if key == "kernel.kptr_restrict":
                return _result("0\n")  # hardening disabled -> drift
            return _result(doctor._HARDENING_SYSCTLS[key] + "\n")

        with mock.patch.object(doctor.runner, "run", side_effect=fake_run):
            c = doctor.check_hardening_sysctls()
            self.assertEqual(c.status, ui.Status.WARN)
            self.assertIn("kptr_restrict", c.detail)

    def test_hardening_sysctls_unavailable_is_info(self):
        missing = runner.Result(["x"], 127, "", "", False, missing=True)
        with mock.patch.object(doctor.runner, "run", return_value=missing):
            self.assertEqual(doctor.check_hardening_sysctls().status, ui.Status.INFO)

    def test_module_blacklist_clean(self):
        lsmod = "Module Size Used by\next4 900 3\nkvm 100 0\n"
        with mock.patch.object(doctor.runner, "run", return_value=_result(lsmod)):
            self.assertEqual(doctor.check_module_blacklist().status, ui.Status.OK)

    def test_module_blacklist_hit(self):
        # firewire_core (underscore form) must match the hyphen form in the list.
        lsmod = "Module Size Used by\ndccp 40 0\nfirewire_core 80 0\n"
        with mock.patch.object(doctor.runner, "run", return_value=_result(lsmod)):
            c = doctor.check_module_blacklist()
            self.assertEqual(c.status, ui.Status.WARN)
            self.assertIn("dccp", c.detail)
            self.assertIn("firewire-core", c.detail)

    def test_apparmor_enforced_count(self):
        with mock.patch.object(doctor.runner, "run", return_value=_result("78\n")):
            c = doctor.check_apparmor_enforced()
            self.assertEqual(c.status, ui.Status.OK)
            self.assertIn("78", c.detail)

    def test_apparmor_enforced_zero_warns(self):
        with mock.patch.object(doctor.runner, "run", return_value=_result("0\n")):
            self.assertEqual(doctor.check_apparmor_enforced().status, ui.Status.WARN)

    def test_listening_external_is_info(self):
        ss = (
            'LISTEN 0 128 0.0.0.0:22 0.0.0.0:* users:(("sshd",pid=850,fd=3))\n'
            'LISTEN 0 128 [::]:22 [::]:* users:(("sshd",pid=850,fd=4))\n'
            'LISTEN 0 4096 127.0.0.1:323 0.0.0.0:* users:(("chronyd",pid=700,fd=5))\n'
        )
        with mock.patch.object(doctor.runner, "run", return_value=_result(ss)):
            c = doctor.check_listening()
        self.assertEqual(c.status, ui.Status.INFO)
        self.assertIn("sshd:22", c.detail)
        self.assertNotIn("chronyd", c.detail)  # loopback excluded
        self.assertIn("1:", c.detail)  # IPv4+IPv6 collapsed to one service

    def test_listening_loopback_only_is_ok(self):
        ss = (
            'LISTEN 0 4096 127.0.0.1:323 0.0.0.0:* users:(("chronyd",pid=700,fd=5))\n'
            'LISTEN 0 128 [::1]:631 [::]:* users:(("cupsd",pid=9,fd=1))\n'
        )
        with mock.patch.object(doctor.runner, "run", return_value=_result(ss)):
            self.assertEqual(doctor.check_listening().status, ui.Status.OK)

    def test_listening_unavailable_is_info(self):
        missing = runner.Result(["x"], 127, "", "", False, missing=True)
        with mock.patch.object(doctor.runner, "run", return_value=missing):
            c = doctor.check_listening()
        self.assertEqual(c.status, ui.Status.INFO)
        self.assertIn("unavailable", c.detail)

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

    def test_run_json_reports_fail(self):
        import json

        fake = [
            doctor.Check("Hardened kernel active", ui.Status.OK, "x-hardened"),
            doctor.Check("Firewall", ui.Status.FAIL, "down"),
            doctor.Check("Arsenal version", ui.Status.INFO, "rolling"),
        ]
        buf = io.StringIO()
        with mock.patch.object(doctor, "gather", return_value=fake), redirect_stdout(buf):
            rc = doctor.run(types.SimpleNamespace(json=True))
        self.assertEqual(rc, 1)
        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(len(payload["checks"]), 3)
        self.assertEqual(payload["checks"][0]["status"], "ok")
        self.assertEqual(payload["summary"]["fail"], 1)

    def test_run_json_ok_when_no_fail(self):
        import json

        fake = [
            doctor.Check("A", ui.Status.OK, ""),
            doctor.Check("B", ui.Status.WARN, "meh"),  # WARN must not fail the run
        ]
        buf = io.StringIO()
        with mock.patch.object(doctor, "gather", return_value=fake), redirect_stdout(buf):
            rc = doctor.run(types.SimpleNamespace(json=True))
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(buf.getvalue())["ok"])


if __name__ == "__main__":
    unittest.main()
