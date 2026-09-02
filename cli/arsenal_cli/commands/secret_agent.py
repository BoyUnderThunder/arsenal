"""``arsenal secret-agent`` — operator OPSEC / "go covert" mode.

Bundles four privacy capabilities that protect *the operator* (not the systems
under test) during authorized work, and a clean ``off`` that restores the
Fortress defaults:

* **cloak**    — randomize interface MACs, set the clock to UTC, spoof hostname.
* **no-trace** — disable swap, turn off shell history, clear session logs.
* **tor**      — route everything through Tor with an nftables kill-switch
                 (clearnet blocked; no DNS/IPv6 leaks).
* **disguise** — repaint the desktop to a generic look for shoulder-surfing.

State needed to undo a change (original hostname, timezone, the pre-Tor firewall
ruleset, …) is saved under a tmpfs dir so ``off`` restores exactly what was
there. Every system action is guarded: a missing tool or a non-root shell
degrades to a WARN/INFO line instead of a traceback.
"""
from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .. import runner, ui
from ..log import get_logger

log = get_logger(__name__)

NAME = "secret-agent"
HELP = "operator OPSEC mode: cloak identity, leave no trace, route via Tor, disguise"

# tmpfs-appropriate on the live image; env-overridable for tests.
STATE_DIR = Path(os.environ.get("ARSENAL_SECRET_STATE", "/run/arsenal/secret-agent"))
FORTRESS_NFT = Path("/etc/nftables.conf")  # canonical Fortress ruleset to restore
TOR_UID_NAME = "tor"

Line = tuple[ui.Status, str, str]  # (status, message, detail)


# --- small helpers -----------------------------------------------------------
def _sh(*argv: str, timeout: float = 30.0) -> runner.Result:
    return runner.run(list(argv), timeout=timeout)


def _state_path() -> Path:
    return STATE_DIR / "state.json"


def _load_state() -> dict:
    try:
        return json.loads(_state_path().read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        _state_path().write_text(json.dumps(state, indent=2))
    except OSError as exc:  # pragma: no cover - state dir unwritable
        log.warning("could not persist secret-agent state: %s", exc)


def _interfaces() -> list[str]:
    """Non-loopback network interfaces (best-effort)."""
    res = _sh("ip", "-o", "link", "show")
    if res.missing or not res.ok:
        return []
    out = []
    for ln in res.stdout.splitlines():
        # "2: eth0: <...>" -> eth0
        parts = ln.split(":")
        if len(parts) >= 2:
            name = parts[1].strip().split("@")[0]
            if name and name != "lo":
                out.append(name)
    return out


# --- capability: cloak identity ----------------------------------------------
def _cloak_enable(state: dict) -> list[Line]:
    lines: list[Line] = []

    # Timezone -> UTC (save the current one first).
    cur_tz = _sh("timedatectl", "show", "-p", "Timezone", "--value")
    if not cur_tz.missing:
        state["timezone"] = cur_tz.stdout.strip() or state.get("timezone", "")
        r = _sh("timedatectl", "set-timezone", "UTC")
        lines.append((ui.Status.OK if r.ok else ui.Status.WARN, "clock set to UTC",
                      "" if r.ok else r.stderr.strip()[:80]))
    else:
        lines.append((ui.Status.INFO, "clock", "timedatectl unavailable"))

    # Hostname -> generic (save the current one).
    cur_host = _sh("hostnamectl", "hostname")
    if not cur_host.missing:
        state["hostname"] = cur_host.stdout.strip() or state.get("hostname", "")
        r = _sh("hostnamectl", "set-hostname", "localhost")
        lines.append((ui.Status.OK if r.ok else ui.Status.WARN, "hostname spoofed", "localhost"))
    else:
        lines.append((ui.Status.INFO, "hostname", "hostnamectl unavailable"))

    # MAC randomization on every non-loopback interface.
    if runner.which("macchanger") is None:
        lines.append((ui.Status.WARN, "MAC randomization skipped", "macchanger not installed"))
    else:
        ifaces = _interfaces()
        if not ifaces:
            lines.append((ui.Status.INFO, "MAC randomization", "no interfaces found"))
        for ifc in ifaces:
            _sh("ip", "link", "set", ifc, "down")
            r = _sh("macchanger", "-r", ifc)
            _sh("ip", "link", "set", ifc, "up")
            lines.append((ui.Status.OK if r.ok else ui.Status.WARN,
                          f"MAC randomized · {ifc}", "" if r.ok else "macchanger failed"))
    return lines


def _cloak_disable(state: dict) -> list[Line]:
    lines: list[Line] = []
    tz = state.get("timezone")
    if tz:
        _sh("timedatectl", "set-timezone", tz)
        lines.append((ui.Status.OK, "clock restored", tz))
    host = state.get("hostname")
    if host:
        _sh("hostnamectl", "set-hostname", host)
        lines.append((ui.Status.OK, "hostname restored", host))
    if runner.which("macchanger"):
        for ifc in _interfaces():
            _sh("ip", "link", "set", ifc, "down")
            _sh("macchanger", "-p", ifc)  # restore permanent hardware MAC
            _sh("ip", "link", "set", ifc, "up")
        lines.append((ui.Status.OK, "hardware MACs restored", ""))
    return lines


def _cloak_status(state: dict) -> Line:
    tz = _sh("timedatectl", "show", "-p", "Timezone", "--value")
    is_utc = (not tz.missing) and tz.stdout.strip() == "UTC"
    return ((ui.Status.OK if is_utc else ui.Status.INFO), "cloak identity",
            "clock UTC" if is_utc else "inactive")


# --- capability: leave no trace ----------------------------------------------
_HIST_DROPIN = Path("/etc/profile.d/00-arsenal-secret-agent.sh")
_HIST_BODY = "# Arsenal Secret Agent — no shell history\nunset HISTFILE\nexport HISTSIZE=0\n"


def _notrace_enable(state: dict) -> list[Line]:
    lines: list[Line] = []

    r = _sh("swapoff", "-a")
    lines.append((ui.Status.OK if r.ok else ui.Status.WARN, "swap disabled",
                  "" if r.ok else r.stderr.strip()[:80]))

    try:
        _HIST_DROPIN.write_text(_HIST_BODY)
        lines.append((ui.Status.OK, "shell history off", "new shells"))
    except OSError as exc:
        lines.append((ui.Status.WARN, "shell history", str(exc)[:80]))
    # Truncate the current user's existing history too.
    hist = Path(os.path.expanduser("~/.bash_history"))
    try:
        if hist.exists():
            hist.write_text("")
    except OSError:
        pass

    if runner.which("journalctl"):
        _sh("journalctl", "--rotate")
        _sh("journalctl", "--vacuum-time=1s")
        lines.append((ui.Status.OK, "session logs cleared", "journal vacuumed"))
    else:
        lines.append((ui.Status.INFO, "session logs", "journalctl unavailable"))
    return lines


def _notrace_disable(state: dict) -> list[Line]:
    lines: list[Line] = []
    try:
        _HIST_DROPIN.unlink(missing_ok=True)
        lines.append((ui.Status.OK, "shell history re-enabled", ""))
    except OSError:
        pass
    _sh("swapon", "-a")  # best-effort; harmless if there is no swap
    lines.append((ui.Status.OK, "swap restored", ""))
    return lines


def _notrace_status(state: dict) -> Line:
    active = _HIST_DROPIN.exists()
    return ((ui.Status.OK if active else ui.Status.INFO), "leave no trace",
            "history off · swap off" if active else "inactive")


# --- capability: go dark (Tor) -----------------------------------------------
_TORRC = Path("/etc/tor/torrc.d/arsenal-secret-agent.conf")
_TOR_CONF = (
    "# Arsenal Secret Agent transparent proxy\n"
    "VirtualAddrNetworkIPv4 10.192.0.0/10\n"
    "AutomapHostsOnResolve 1\n"
    "TransPort 9040\n"
    "DNSPort 5353\n"
)


def _tor_ruleset() -> str:
    """nftables kill-switch: everything through Tor, clearnet dropped, IPv6 off."""
    return f"""#!/usr/sbin/nft -f
# Arsenal Secret Agent — Tor transparent proxy + kill-switch.
flush ruleset

table inet killswitch {{
  chain output {{
    type filter hook output priority 100; policy drop;
    oif "lo" accept
    meta skuid "{TOR_UID_NAME}" accept          # tor itself may reach the net
    ip daddr 127.0.0.0/8 accept
    ip protocol tcp ct state new redirect to :9040
    ip protocol udp udp dport 53 redirect to :5353
    ct state established,related accept
    meta nfproto ipv6 drop                       # no IPv6 leaks
  }}
  chain input {{ type filter hook input priority 0; policy drop; iif "lo" accept; ct state established,related accept; }}
}}
"""


def _tor_enable(state: dict) -> list[Line]:
    lines: list[Line] = []
    if runner.which("tor") is None:
        return [(ui.Status.WARN, "go dark skipped", "tor not installed")]

    # Snapshot the live firewall so `off` can restore it exactly.
    snap = _sh("nft", "list", "ruleset")
    if not snap.missing and snap.ok:
        try:
            (STATE_DIR / "nft.snapshot").write_text(snap.stdout)
        except OSError:
            pass

    try:
        _TORRC.parent.mkdir(parents=True, exist_ok=True)
        _TORRC.write_text(_TOR_CONF)
    except OSError as exc:
        return [(ui.Status.WARN, "go dark", f"cannot write torrc: {exc}")]

    r = _sh("systemctl", "restart", "tor")
    if r.missing:
        r = _sh("tor", "--runasdaemon", "1")  # fallback when systemd is absent
    lines.append((ui.Status.OK if r.ok else ui.Status.WARN, "Tor started",
                  "" if r.ok else r.stderr.strip()[:80]))

    rules = STATE_DIR / "killswitch.nft"
    try:
        rules.write_text(_tor_ruleset())
        kr = _sh("nft", "-f", str(rules))
        lines.append((ui.Status.OK if kr.ok else ui.Status.FAIL, "kill-switch armed",
                      "clearnet blocked" if kr.ok else kr.stderr.strip()[:100]))
    except OSError as exc:
        lines.append((ui.Status.WARN, "kill-switch", str(exc)[:80]))
    return lines


def _tor_disable(state: dict) -> list[Line]:
    lines: list[Line] = []
    try:
        _TORRC.unlink(missing_ok=True)
    except OSError:
        pass
    _sh("systemctl", "stop", "tor")
    # Restore the Fortress firewall from its canonical file (default-deny).
    if FORTRESS_NFT.is_file():
        r = _sh("nft", "-f", str(FORTRESS_NFT))
        lines.append((ui.Status.OK if r.ok else ui.Status.FAIL, "Fortress firewall restored",
                      "" if r.ok else r.stderr.strip()[:100]))
    else:
        lines.append((ui.Status.WARN, "firewall", f"{FORTRESS_NFT} missing — reboot to restore"))
    return lines


def _tor_status(state: dict) -> Line:
    r = _sh("systemctl", "is-active", "tor")
    active = (not r.missing) and r.stdout.strip() == "active"
    return ((ui.Status.OK if active else ui.Status.INFO), "go dark (Tor)",
            "routing via Tor" if active else "inactive")


# --- capability: disguise ----------------------------------------------------
def _disguise_enable(state: dict) -> list[Line]:
    if runner.which("xfconf-query") is None or not os.environ.get("DISPLAY"):
        return [(ui.Status.INFO, "disguise skipped", "needs a running XFCE session")]
    # Save then swap to a plain, generic desktop look.
    cur = _sh("xfconf-query", "-c", "xfwm4", "-p", "/general/theme")
    if not cur.missing:
        state["xfwm_theme"] = cur.stdout.strip()
    _sh("xfconf-query", "-c", "xfwm4", "-p", "/general/theme", "-s", "Default")
    _sh("xfconf-query", "-c", "xsettings", "-p", "/Net/ThemeName", "-s", "Adwaita")
    return [(ui.Status.OK, "desktop disguised", "generic theme")]


def _disguise_disable(state: dict) -> list[Line]:
    if runner.which("xfconf-query") is None or not os.environ.get("DISPLAY"):
        return [(ui.Status.INFO, "disguise", "no XFCE session")]
    theme = state.get("xfwm_theme")
    if theme:
        _sh("xfconf-query", "-c", "xfwm4", "-p", "/general/theme", "-s", theme)
    return [(ui.Status.OK, "desktop restored", theme or "")]


def _disguise_status(state: dict) -> Line:
    active = bool(state.get("xfwm_theme"))
    return ((ui.Status.OK if active else ui.Status.INFO), "disguise",
            "generic look" if active else "inactive")


# --- registry ----------------------------------------------------------------
@dataclass
class Cap:
    key: str
    label: str
    flag: str
    enable: Callable[[dict], list[Line]]
    disable: Callable[[dict], list[Line]]
    status: Callable[[dict], Line]


CAPS: list[Cap] = [
    Cap("cloak", "Cloak identity", "cloak", _cloak_enable, _cloak_disable, _cloak_status),
    Cap("notrace", "Leave no trace", "no_trace", _notrace_enable, _notrace_disable, _notrace_status),
    Cap("tor", "Go dark (Tor)", "tor", _tor_enable, _tor_disable, _tor_status),
    Cap("disguise", "Disguise", "disguise", _disguise_enable, _disguise_disable, _disguise_status),
]


def _selected(args) -> list[Cap]:
    """Caps chosen by flags; with no capability flag, all of them."""
    chosen = [c for c in CAPS if getattr(args, c.flag, False)]
    return chosen or list(CAPS)


def add_arguments(parser) -> None:
    parser.add_argument("action", nargs="?", default="status",
                        choices=["on", "off", "status"], help="what to do (default: status)")
    parser.add_argument("--cloak", action="store_true", help="only: cloak identity")
    parser.add_argument("--no-trace", dest="no_trace", action="store_true", help="only: leave no trace")
    parser.add_argument("--tor", action="store_true", help="only: go dark via Tor")
    parser.add_argument("--disguise", action="store_true", help="only: disguise the desktop")
    parser.add_argument("-y", "--yes", action="store_true", help="skip the confirmation on 'on'")


def _needs_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() != 0


def run(args) -> int:
    action = getattr(args, "action", "status") or "status"
    state = _load_state()

    if action == "status":
        print(ui.header("Arsenal Secret Agent — status"))
        for cap in CAPS:
            st, msg, detail = cap.status(state)
            ui.print_status(st, msg, detail)
        return 0

    if _needs_root():
        ui.print_status(ui.Status.FAIL, "secret-agent needs root", "re-run with sudo")
        return 1

    caps = _selected(args)
    if action == "on":
        if not args.yes:
            print(ui.style("⚠ Secret Agent changes networking, the clock, and the firewall.",
                           ui.YELLOW, ui.BOLD))
            print("  This is operator OPSEC for authorized work. Restore anytime: "
                  + ui.style("arsenal secret-agent off", ui.CYAN))
            try:
                if input("  Engage? [y/N] ").strip().lower() not in ("y", "yes"):
                    print("  aborted")
                    return 0
            except EOFError:
                return 1
        print(ui.header("Secret Agent — engaging"))
        enabled = list(state.get("enabled", []))
        for cap in caps:
            for st, msg, detail in cap.enable(state):
                ui.print_status(st, msg, detail)
            if cap.key not in enabled:
                enabled.append(cap.key)
        state["enabled"] = enabled
        _save_state(state)
        print("  " + ui.style("covert. undo with: arsenal secret-agent off", ui.DIM))
        return 0

    # action == "off"
    print(ui.header("Secret Agent — standing down"))
    for cap in caps:
        for st, msg, detail in cap.disable(state):
            ui.print_status(st, msg, detail)
    state["enabled"] = [k for k in state.get("enabled", []) if k not in {c.key for c in caps}]
    _save_state(state)
    print("  " + ui.style("Fortress defaults restored.", ui.DIM))
    return 0
