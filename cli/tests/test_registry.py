"""Guard the weapon registry — the single source of truth that drives both the
profile.d login launchers and ``arsenal armory``.

A malformed or clashing line here silently breaks a launcher on the live ISO,
so this test asserts the invariants against the *real* registry file shipped in
the profile (not a fixture): 4 non-empty fields per line, unique weapon names,
a safe command-name charset, and no shadowing of critical shell commands.
"""
import re
import unittest
from pathlib import Path

REGISTRY = (
    Path(__file__).resolve().parents[2]
    / "profile" / "airootfs" / "usr" / "local" / "share" / "arsenal" / "registry"
)

# A weapon name becomes a login command (profile.d launcher), so it must not
# shadow anything an operator relies on.
_RESERVED = frozenset({
    "arsenal", "ls", "cd", "cp", "mv", "rm", "cat", "echo", "sudo", "su", "sh",
    "bash", "exit", "kill", "pkill", "reboot", "poweroff", "shutdown", "mount",
    "umount", "dd", "chmod", "chown", "ln", "ps", "top", "man", "git", "vim",
    "nano", "clear", "history", "export", "source", "sysctl", "systemctl",
})
_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def _data_lines():
    for lineno, raw in enumerate(REGISTRY.read_text().splitlines(), 1):
        line = raw.strip()
        if line and not line.startswith("#"):
            yield lineno, line


class TestRegistry(unittest.TestCase):
    def test_registry_exists_and_nonempty(self):
        self.assertTrue(REGISTRY.is_file(), f"registry missing at {REGISTRY}")
        self.assertTrue(list(_data_lines()), "registry has no weapon entries")

    def test_every_line_has_four_nonempty_fields(self):
        for lineno, line in _data_lines():
            parts = line.split("|")
            self.assertGreaterEqual(
                len(parts), 4, f"line {lineno}: expected 4 fields, got {len(parts)}: {line!r}"
            )
            for idx, field in enumerate(parts[:4]):
                self.assertTrue(
                    field.strip(), f"line {lineno}: field {idx + 1} is empty: {line!r}"
                )

    def test_weapon_names_unique(self):
        seen: dict[str, int] = {}
        for lineno, line in _data_lines():
            name = line.split("|", 1)[0].strip()
            self.assertNotIn(name, seen, f"duplicate weapon {name!r} (lines {seen.get(name)} & {lineno})")
            seen[name] = lineno

    def test_weapon_names_are_safe_command_names(self):
        for lineno, line in _data_lines():
            name = line.split("|", 1)[0].strip()
            self.assertRegex(name, _NAME_RE, f"line {lineno}: unsafe weapon name {name!r}")
            self.assertNotIn(
                name, _RESERVED, f"line {lineno}: weapon {name!r} shadows a critical command"
            )

    def test_matches_armory_parser(self):
        # The CLI's own parser must accept every line (kept in lock-step so the
        # table and the launchers never disagree about what's a valid entry).
        from arsenal_cli.commands import armory

        parsed = list(armory._iter_registry(REGISTRY.read_text()))
        self.assertEqual(len(parsed), len(list(_data_lines())))
        for weapon, binary, category, desc in parsed:
            self.assertTrue(all([weapon, binary, category, desc]))


if __name__ == "__main__":
    unittest.main()
