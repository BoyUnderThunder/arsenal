"""``arsenal doctor`` — system health & security diagnostics.

Each check is an independent function returning a :class:`Check`; one failing
check can never abort the whole report. The command's exit code is 0 unless any
check is FAIL (so it is usable in scripts and CI).
"""
from __future__ import annotations

import json
import os
import shutil
import socket
from collections.abc import Callable
from dataclasses import dataclass

from .. import runner, ui
from ..log import get_logger
from ..version import os_version

log = get_logger(__name__)


@dataclass
class Check:
    name: str
    status: ui.Status
    detail: str = ""


# --- individual checks -------------------------------------------------------
def check_kernel() -> Check:
    release = os.uname().release
    if "hardened" in release:
        return Check("Hardened kernel active", ui.Status.OK, release)
    return Check("Hardened kernel", ui.Status.FAIL, f"running {release} (not linux-hardened)")


def check_apparmor() -> Check:
    if not os.path.exists("/sys/module/apparmor"):
        return Check("AppArmor", ui.Status.FAIL, "kernel module not loaded")
    active = runner.run(["systemctl", "is-active", "apparmor"], timeout=10).stdout.strip()
    profiled = runner.run(["aa-status", "--profiled"], timeout=10)
    detail = f"{profiled.stdout.strip()} profiles" if profiled.ok and profiled.stdout.strip() else "module loaded"
    if active == "active" or os.path.exists("/sys/kernel/security/apparmor"):
        return Check("AppArmor enabled", ui.Status.OK, detail)
    return Check("AppArmor", ui.Status.WARN, "module present but service inactive")


def check_firewall() -> Check:
    active = runner.run(["systemctl", "is-active", "nftables"], timeout=10).stdout.strip()
    ruleset = runner.run(["nft", "list", "ruleset"], timeout=10)
    default_deny = "policy drop" in ruleset.stdout
    # The loaded ruleset is the ground truth for whether the firewall is up: a
    # default-deny policy blocks inbound traffic even when nftables.service reads
    # "inactive" — it is a oneshot that exits after loading rules, which is normal
    # on the live ISO. Only treat the firewall as down when no default-deny
    # policy is present at all.
    if default_deny:
        detail = "nftables, default-deny" if active == "active" else f"nftables, default-deny (service {active or 'inactive'})"
        return Check("Firewall active (default-deny)", ui.Status.OK, detail)
    if active == "active":
        return Check("Firewall active", ui.Status.WARN, "nftables up but no default-deny policy")
    return Check("Firewall", ui.Status.FAIL, "nftables inactive, no default-deny ruleset")


# Kernel-hardening sysctls Arsenal ships in
# etc/sysctl.d/99-arsenal-hardening.conf — the security-relevant subset.
# Keep in sync with that file.
_HARDENING_SYSCTLS: dict[str, str] = {
    "kernel.kptr_restrict": "2",
    "kernel.dmesg_restrict": "1",
    "kernel.yama.ptrace_scope": "1",
    "kernel.unprivileged_bpf_disabled": "1",
    "net.core.bpf_jit_harden": "2",
    "kernel.perf_event_paranoid": "3",
    "fs.suid_dumpable": "0",
    "fs.protected_symlinks": "1",
    "fs.protected_hardlinks": "1",
}


def check_hardening_sysctls() -> Check:
    """Verify Arsenal's kernel-hardening sysctls are applied at runtime.

    Posture reporting only: WARN (never FAIL) on drift, since the boot-time
    self-test already gates the build on the critical values and doctor's exit
    code must stay usable in scripts.
    """
    mismatched: list[str] = []
    unavailable = 0
    for key, want in _HARDENING_SYSCTLS.items():
        res = runner.run(["sysctl", "-n", key], timeout=10)
        if res.missing:
            unavailable += 1
            continue
        got = res.stdout.strip()
        if got != want:
            mismatched.append(f"{key}={got or '?'}≠{want}")
    total = len(_HARDENING_SYSCTLS)
    if unavailable == total:
        return Check("Kernel hardening sysctls", ui.Status.INFO, "sysctl unavailable")
    if not mismatched:
        return Check("Kernel hardening sysctls applied", ui.Status.OK, f"{total} values")
    shown = ", ".join(mismatched[:3])
    more = "" if len(mismatched) <= 3 else f" (+{len(mismatched) - 3} more)"
    return Check("Kernel hardening sysctls", ui.Status.WARN, f"{len(mismatched)}/{total} not applied: {shown}{more}")


# Kernel modules Arsenal blacklists in etc/modprobe.d/arsenal-blacklist.conf —
# rarely-used, historically-abused protocols/filesystems. Keep in sync.
_BLACKLISTED_MODULES: frozenset[str] = frozenset(
    {
        "dccp", "sctp", "rds", "tipc",
        "cramfs", "freevxfs", "jffs2", "hfs", "hfsplus", "udf",
        "firewire-core", "thunderbolt",
    }
)


def check_module_blacklist() -> Check:
    """WARN if any blacklisted attack-surface kernel module is loaded."""
    res = runner.run(["lsmod"], timeout=10)
    if res.missing:
        return Check("Module blacklist", ui.Status.INFO, "lsmod unavailable")
    # lsmod names use underscores; the blacklist uses hyphens — normalise both.
    loaded = {ln.split()[0].replace("-", "_") for ln in res.stdout.splitlines()[1:] if ln.split()}
    hits = sorted(m for m in _BLACKLISTED_MODULES if m.replace("-", "_") in loaded)
    if not hits:
        return Check("Module blacklist enforced", ui.Status.OK, f"{len(_BLACKLISTED_MODULES)} modules")
    return Check("Module blacklist", ui.Status.WARN, "loaded: " + ", ".join(hits))


def check_apparmor_enforced() -> Check:
    """Report how many AppArmor profiles are in enforce mode."""
    res = runner.run(["aa-status", "--enforced"], timeout=10)
    if res.missing:
        return Check("AppArmor enforce mode", ui.Status.INFO, "aa-status unavailable")
    tok = res.stdout.strip().split()
    n = int(tok[0]) if tok and tok[0].isdigit() else 0
    if n > 0:
        return Check("AppArmor enforce mode", ui.Status.OK, f"{n} profiles enforced")
    return Check("AppArmor enforce mode", ui.Status.WARN, "no profiles in enforce mode")


def check_blackarch() -> Check:
    listing = runner.run(["pacman", "-Sl", "blackarch"], timeout=20)
    if listing.missing:
        return Check("BlackArch repository", ui.Status.INFO, "pacman unavailable")
    if listing.ok and listing.stdout.strip():
        n = sum(1 for _ in listing.stdout.splitlines())
        return Check("BlackArch repository configured", ui.Status.OK, f"{n} packages")
    return Check("BlackArch repository", ui.Status.WARN, "not configured or DB not synced")


def check_internet() -> Check:
    for host in ("1.1.1.1", "8.8.8.8"):
        try:
            with socket.create_connection((host, 53), timeout=4):
                return Check("Internet connectivity", ui.Status.OK, f"reached {host}:53")
        except OSError:
            continue
    return Check("Internet connectivity", ui.Status.WARN, "no outbound connection")


def check_disk() -> Check:
    # On the live ISO, `/` is an overlay whose writable layer is a RAM-backed
    # cowspace; statvfs("/") can report the read-only squashfs (~0 free), a
    # false alarm. Measure the writable cowspace instead when it is mounted.
    path = "/run/archiso/cowspace" if os.path.ismount("/run/archiso/cowspace") else "/"
    total, _used, free = shutil.disk_usage(path)
    free_gb = free / 1e9
    pct = free / total * 100 if total else 0
    status = ui.Status.OK if free_gb > 5 else ui.Status.WARN if free_gb > 1 else ui.Status.FAIL
    return Check("Disk space", status, f"{free_gb:.1f} GB free ({pct:.0f}%) on {path}")


def check_memory() -> Check:
    try:
        info: dict[str, int] = {}
        with open("/proc/meminfo") as fh:
            for line in fh:
                key, _, value = line.partition(":")
                info[key] = int(value.split()[0])
        total, avail = info["MemTotal"], info["MemAvailable"]
        avail_gb = avail / 1e6
        pct = avail / total * 100 if total else 0
        status = ui.Status.OK if pct > 15 else ui.Status.WARN
        return Check("Memory", status, f"{avail_gb:.1f} GB available ({pct:.0f}%)")
    except (OSError, KeyError, ValueError, IndexError):
        return Check("Memory", ui.Status.INFO, "unavailable")


def check_version() -> Check:
    return Check("Arsenal version", ui.Status.INFO, os_version())


def check_updates() -> Check:
    if runner.which("checkupdates"):
        res = runner.run(["checkupdates"], timeout=90)
        pending = [ln for ln in res.stdout.splitlines() if ln.strip()]
    else:
        res = runner.run(["pacman", "-Qu"], timeout=90)
        if res.missing:
            return Check("Pending updates", ui.Status.INFO, "pacman unavailable")
        pending = [ln for ln in res.stdout.splitlines() if ln.strip()]
    if pending:
        return Check("Updates available", ui.Status.WARN, f"{len(pending)} package(s) — run: arsenal update")
    return Check("System up to date", ui.Status.OK)


def check_integrity() -> Check:
    res = runner.run(["pacman", "-Qkk"], timeout=180)
    if res.missing:
        return Check("Package integrity", ui.Status.INFO, "pacman unavailable")
    problems = [ln for ln in (res.stdout + res.stderr).splitlines() if "warning:" in ln or "error:" in ln]
    if res.ok and not problems:
        return Check("Package integrity verified", ui.Status.OK)
    return Check("Package integrity", ui.Status.WARN, f"{len(problems)} file warning(s)")


def check_services() -> Check:
    critical = ["apparmor", "nftables"]
    inactive = [
        svc
        for svc in critical
        if runner.run(["systemctl", "is-active", svc], timeout=10).stdout.strip() != "active"
    ]
    if not inactive:
        return Check("Critical services running", ui.Status.OK, ", ".join(critical))
    return Check("Critical services", ui.Status.WARN, "inactive: " + ", ".join(inactive))


CHECKS: list[Callable[[], Check]] = [
    check_kernel,
    check_apparmor,
    check_firewall,
    check_hardening_sysctls,
    check_module_blacklist,
    check_apparmor_enforced,
    check_blackarch,
    check_internet,
    check_disk,
    check_memory,
    check_version,
    check_updates,
    check_integrity,
    check_services,
]


def gather() -> list[Check]:
    """Run every check, isolating failures."""
    results: list[Check] = []
    for chk in CHECKS:
        try:
            results.append(chk())
        except Exception as exc:  # a broken check must not sink the report
            log.exception("check %s raised", getattr(chk, "__name__", chk))
            results.append(Check(getattr(chk, "__name__", "check").replace("check_", ""), ui.Status.INFO, f"check error: {exc}"))
    return results


def run(args) -> int:
    results = gather()
    worst = ui.Status.OK
    for c in results:
        if ui.SEVERITY[c.status] > ui.SEVERITY[worst]:
            worst = c.status
    rc = 1 if worst == ui.Status.FAIL else 0

    # Machine-readable output for monitoring / scripting / the dashboard.
    if getattr(args, "json", False):
        payload = {
            "checks": [
                {"name": c.name, "status": c.status.value, "detail": c.detail}
                for c in results
            ],
            "summary": {s.value: sum(1 for c in results if c.status == s) for s in ui.Status},
            "ok": rc == 0,
        }
        print(json.dumps(payload, indent=2))
        return rc

    print(ui.header("Arsenal Doctor"))
    for c in results:
        ui.print_status(c.status, c.name, c.detail)
    counts = {s: sum(1 for c in results if c.status == s) for s in ui.Status}
    print()
    print(
        "  "
        + ui.style(
            f"{counts[ui.Status.OK]} ok · {counts[ui.Status.WARN]} warnings · "
            f"{counts[ui.Status.FAIL]} failures",
            ui.DIM,
        )
    )
    return rc
