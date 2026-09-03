import io
import json
import shutil
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from arsenal_cli import runner, ui
from arsenal_cli.commands import secret_agent as sa


def ok(stdout=""):
    return runner.Result(["x"], 0, stdout, "", True)


def _args(action="status", **kw):
    base = {"action": action, "cloak": False, "no_trace": False, "tor": False,
            "disguise": False, "yes": True}
    base.update(kw)
    return types.SimpleNamespace(**base)


class TestSecretAgent(unittest.TestCase):
    def setUp(self):
        ui.set_color(False)
        self.td = tempfile.mkdtemp()
        self._patchers = [
            mock.patch.object(sa, "STATE_DIR", Path(self.td) / "state"),
            mock.patch.object(sa, "_HIST_DROPIN", Path(self.td) / "hist.sh"),
            mock.patch.object(sa, "_TORRC", Path(self.td) / "torrc"),
            mock.patch.object(sa, "FORTRESS_NFT", Path(self.td) / "nftables.conf"),
        ]
        for p in self._patchers:
            p.start()

    def tearDown(self):
        for p in self._patchers:
            p.stop()
        shutil.rmtree(self.td, ignore_errors=True)

    def _run(self, args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = sa.run(args)
        return rc, buf.getvalue()

    def test_status_lists_all_caps(self):
        with mock.patch.object(sa.runner, "run", return_value=ok("America/NY")):
            rc, out = self._run(_args("status"))
        self.assertEqual(rc, 0)
        for label in ("cloak identity", "leave no trace", "go dark", "disguise"):
            self.assertIn(label, out)

    def test_on_requires_root(self):
        with mock.patch.object(sa.os, "geteuid", return_value=1000, create=True):
            rc, out = self._run(_args("on"))
        self.assertEqual(rc, 1)
        self.assertIn("root", out)

    def test_on_all_enables_and_persists_state(self):
        with mock.patch.object(sa.os, "geteuid", return_value=0, create=True), \
             mock.patch.object(sa.runner, "which", return_value="/usr/bin/x"), \
             mock.patch.object(sa.runner, "run", return_value=ok("UTC")):
            rc, _ = self._run(_args("on", yes=True))
        self.assertEqual(rc, 0)
        state = json.loads((sa.STATE_DIR / "state.json").read_text())
        self.assertEqual(set(state["enabled"]), {"cloak", "notrace", "tor", "disguise"})

    def test_off_restores_fortress_and_clears_state(self):
        sa.STATE_DIR.mkdir(parents=True, exist_ok=True)
        (sa.STATE_DIR / "state.json").write_text(json.dumps(
            {"enabled": ["cloak", "notrace", "tor", "disguise"], "timezone": "UTC", "hostname": "h"}))
        sa.FORTRESS_NFT.write_text("flush ruleset\n")
        calls = []
        with mock.patch.object(sa.os, "geteuid", return_value=0, create=True), \
             mock.patch.object(sa.runner, "which", return_value="/usr/bin/x"), \
             mock.patch.object(sa.runner, "run", side_effect=lambda cmd, timeout=30.0: calls.append(cmd) or ok()):
            rc, out = self._run(_args("off"))
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads((sa.STATE_DIR / "state.json").read_text())["enabled"], [])
        # the Fortress ruleset file was reloaded
        self.assertIn(["nft", "-f", str(sa.FORTRESS_NFT)], calls)

    def test_selected_flags(self):
        self.assertEqual([c.key for c in sa._selected(_args("on", tor=True))], ["tor"])
        self.assertEqual(len(sa._selected(_args("on"))), 4)  # no flag -> all

    def test_cloak_enable_saves_and_sets_utc(self):
        calls = []

        def fake(cmd, timeout=30.0):
            calls.append(cmd)
            if cmd[:3] == ["timedatectl", "show", "-p"]:
                return ok("America/New_York")
            if cmd[:2] == ["hostnamectl", "hostname"]:
                return ok("myhost")
            return ok()

        state = {}
        with mock.patch.object(sa.runner, "which", return_value=None), \
             mock.patch.object(sa.runner, "run", side_effect=fake):
            sa._cloak_enable(state)
        self.assertEqual(state["timezone"], "America/New_York")
        self.assertEqual(state["hostname"], "myhost")
        self.assertIn(["timedatectl", "set-timezone", "UTC"], calls)

    def test_tor_enable_snapshots_and_arms_killswitch(self):
        sa.STATE_DIR.mkdir(parents=True, exist_ok=True)
        with mock.patch.object(sa.runner, "which", return_value="/usr/bin/tor"), \
             mock.patch.object(sa.runner, "run", return_value=ok("table inet fortress { }")):
            lines = sa._tor_enable({})
        self.assertTrue((sa.STATE_DIR / "nft.snapshot").exists())   # firewall snapshotted for restore
        self.assertTrue((sa.STATE_DIR / "killswitch.nft").exists())
        self.assertTrue(any("kill-switch" in msg for _, msg, _ in lines))

    def test_tor_enable_skips_without_tor(self):
        with mock.patch.object(sa.runner, "which", return_value=None):
            lines = sa._tor_enable({})
        self.assertEqual(lines[0][0], ui.Status.WARN)
        self.assertIn("tor not installed", lines[0][2])


if __name__ == "__main__":
    unittest.main()
