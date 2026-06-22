#!/usr/bin/env bash
# =============================================================================
#  Arsenal post-boot integration test
# =============================================================================
#  Goes beyond smoke-test.sh ("does it reach a shell?") and proves the Fortress
#  is actually LIVE, not just configured. Boots the ISO headless (direct kernel
#  boot + the ISO as a CD, like the smoke test), drives the autologin serial
#  root shell over a FIFO, and asserts the security posture:
#
#    * linux-hardened kernel running          (uname -r contains "hardened")
#    * AppArmor loaded & service active        (/sys/module/apparmor, systemctl)
#    * nftables ruleset has input policy drop  (nft list ruleset)
#    * key sysctls applied                     (kptr_restrict, ptrace_scope, bpf)
#    * arsenal doctor exits 0
#    * a sample of weapons map to their tools  (sniper/tower/hunter)
#
#  Exits non-zero if any assertion fails, so CI turns "it boots" into "it boots
#  with the security posture proven."
#
#  Must run as root (loop-mounts the ISO). Uses KVM if available, else TCG.
#  Usage: sudo tools/integration-test.sh path/to/arsenal.iso [boot_timeout_s]
# =============================================================================
set -euo pipefail

ISO="${1:?usage: integration-test.sh <iso> [boot_timeout]}"
BOOT_TIMEOUT="${2:-900}"
[[ -f "${ISO}" ]] || { echo "integration-test: ISO not found: ${ISO}" >&2; exit 2; }
command -v qemu-system-x86_64 >/dev/null || { echo "integration-test: qemu-system-x86_64 missing" >&2; exit 2; }
[[ ${EUID} -eq 0 ]] || { echo "integration-test: must run as root (mounts the ISO)" >&2; exit 2; }

MEM="${SMOKE_MEM:-4096}"
WORK="$(mktemp -d)"
LOG="${WORK}/serial.log"
IN="${WORK}/in.fifo"
MNT="${WORK}/mnt"; mkdir -p "${MNT}"
mkfifo "${IN}"
NONCE="${RANDOM}${RANDOM}"
QPID=""

cleanup() {
    [[ -n "${QPID}" ]] && kill "${QPID}" 2>/dev/null || true
    exec 3>&- 2>/dev/null || true
    mountpoint -q "${MNT}" && umount "${MNT}" 2>/dev/null || true
    rm -rf "${WORK}" 2>/dev/null || true
}
trap cleanup EXIT

FAIL_RE='Kernel panic|Unable to mount root|Attempted to kill init|Cannot open root|Entering emergency|You are in emergency'

# --- Extract kernel + initramfs (+ microcode) from the ISO --------------------
LABEL="$(blkid -o value -s LABEL "${ISO}" 2>/dev/null || echo '')"
mount -o loop,ro "${ISO}" "${MNT}"
VMLINUZ="$(find "${MNT}" -name 'vmlinuz-linux-hardened' | head -1)"
INITRD="$(find "${MNT}" -name 'initramfs-linux-hardened.img' | head -1)"
UCODE="$(find "${MNT}" -name '*-ucode.img' | sort | tr '\n' ' ')"
[[ -n "${VMLINUZ}" && -n "${INITRD}" ]] || { echo "integration-test: kernel/initramfs not found on ISO" >&2; exit 2; }
BASEDIR="${VMLINUZ#"${MNT}"/}"; BASEDIR="${BASEDIR%%/*}"
cp "${VMLINUZ}" "${WORK}/vmlinuz"
# shellcheck disable=SC2086
cat ${UCODE} "${INITRD}" > "${WORK}/initrd.img"
umount "${MNT}"

ACCEL=(-accel tcg)
if [[ -w /dev/kvm ]]; then ACCEL=(-enable-kvm -cpu host); echo "integration-test: using KVM"; else echo "integration-test: using TCG (slow)"; fi

# --- Boot, with a writable serial (FIFO -> guest stdin, log <- guest stdout) --
exec 3<>"${IN}"   # keep the FIFO open read-write so our writes never EOF
echo "integration-test: booting ${ISO} (label=${LABEL}, basedir=${BASEDIR})"
qemu-system-x86_64 "${ACCEL[@]}" -m "${MEM}" -smp 2 \
    -kernel "${WORK}/vmlinuz" -initrd "${WORK}/initrd.img" \
    -append "archisobasedir=${BASEDIR} archisolabel=${LABEL} console=ttyS0,115200 cow_spacesize=1G" \
    -cdrom "${ISO}" -display none -serial stdio -monitor none -no-reboot < "${IN}" > "${LOG}" 2>&1 &
QPID=$!

# wait_for <pattern> <timeout_s>: succeed when pattern appears; fail on panic/exit
wait_for() {
    local pat="$1" t="$2" end; end=$(( $(date +%s) + t ))
    while [[ $(date +%s) -lt ${end} ]]; do
        kill -0 "${QPID}" 2>/dev/null || { echo "integration-test: QEMU exited early" >&2; return 1; }
        grep -qaE "${pat}" "${LOG}" && return 0
        grep -qaiE "${FAIL_RE}" "${LOG}" && { echo "integration-test: boot-failure signature on serial" >&2; return 1; }
        sleep 3
    done
    return 1
}

dump_tail() { echo "----- serial log (tail 60) -----"; tail -n 60 "${LOG}" 2>/dev/null | tr -d '\000\r' || true; echo "--------------------------------"; }

# --- Wait for autologin shell, then confirm it accepts input -----------------
if ! wait_for 'root@arsenal' "${BOOT_TIMEOUT}"; then
    echo "integration-test: never reached the autologin root shell" >&2; dump_tail; exit 1
fi
sleep 3
printf '\necho ARSENAL_RDY_%s\n' "${NONCE}" >&3
if ! wait_for "ARSENAL_RDY_${NONCE}" 90; then
    echo "integration-test: serial shell not responding to input" >&2; dump_tail; exit 1
fi

# --- Send the assertion batch (each line runs in the guest root shell) --------
# Single-quoted on the host so the guest expands $(...) itself.
CMDS=(
    'printf "ITRES uname=%s\n" "$(uname -r)"'
    'printf "ITRES kptr=%s\n" "$(sysctl -n kernel.kptr_restrict 2>/dev/null)"'
    'printf "ITRES ptrace=%s\n" "$(sysctl -n kernel.yama.ptrace_scope 2>/dev/null)"'
    'printf "ITRES bpf=%s\n" "$(sysctl -n net.core.bpf_jit_harden 2>/dev/null)"'
    'printf "ITRES nftdrop=%s\n" "$(nft list ruleset 2>/dev/null | grep -c "policy drop")"'
    'printf "ITRES aamod=%s\n" "$([ -d /sys/module/apparmor ] && echo 1 || echo 0)"'
    'printf "ITRES aaactive=%s\n" "$(systemctl is-active apparmor 2>/dev/null)"'
    'printf "ITRES aaenf=%s\n" "$(aa-status --enforced 2>/dev/null || echo 0)"'
    'arsenal doctor >/dev/null 2>&1; printf "ITRES doctorrc=%s\n" "$?"'
    'printf "ITRES sniper=%s\n" "$(type sniper 2>/dev/null | grep -c nmap)"'
    'printf "ITRES tower=%s\n" "$(type tower 2>/dev/null | grep -c burpsuite)"'
    'printf "ITRES hunter=%s\n" "$(type hunter 2>/dev/null | grep -c bloodhound)"'
)
for c in "${CMDS[@]}"; do printf '%s\n' "${c}" >&3; done
printf 'echo ITDONE_%s\n' "${NONCE}" >&3

if ! wait_for "ITDONE_${NONCE}" 180; then
    echo "integration-test: assertions did not complete in time" >&2; dump_tail; exit 1
fi

# --- Parse + assert -----------------------------------------------------------
CLEAN="${WORK}/clean.log"; tr -d '\000\r' < "${LOG}" > "${CLEAN}"
echo "----- captured posture -----"; grep -aE '^ITRES ' "${CLEAN}" | sort -u; echo "----------------------------"

getval() { grep -aE "^ITRES $1=" "${CLEAN}" | tail -1 | sed -E "s/^ITRES $1=//"; }

fails=0
check() { # name  test-expression  observed
    if eval "$2"; then printf '[PASS] %-28s %s\n' "$1" "$3"
    else printf '[FAIL] %-28s %s\n' "$1" "$3"; fails=$((fails + 1)); fi
}

u="$(getval uname)";        check "hardened kernel"        '[[ "$u" == *hardened* ]]'        "${u:-<none>}"
kptr="$(getval kptr)";      check "kptr_restrict=2"        '[[ "$kptr" == "2" ]]'           "${kptr:-<none>}"
ptr="$(getval ptrace)";     check "yama.ptrace_scope=1"    '[[ "$ptr" == "1" ]]'            "${ptr:-<none>}"
bpf="$(getval bpf)";        check "bpf_jit_harden=2"       '[[ "$bpf" == "2" ]]'            "${bpf:-<none>}"
nft="$(getval nftdrop)";    check "nftables policy drop"   '[[ "${nft:-0}" -ge 1 ]]'        "${nft:-<none>} match(es)"
aam="$(getval aamod)";      check "AppArmor module loaded" '[[ "$aam" == "1" ]]'            "${aam:-<none>}"
aaa="$(getval aaactive)";   check "apparmor.service active" '[[ "$aaa" == "active" ]]'      "${aaa:-<none>}"
aae="$(getval aaenf)";      check "AppArmor enforcing >=1" '[[ "${aae:-0}" -ge 1 ]]'        "${aae:-<none>} profile(s)"
dr="$(getval doctorrc)";    check "arsenal doctor exit 0"  '[[ "$dr" == "0" ]]'             "rc=${dr:-<none>}"
sn="$(getval sniper)";      check "weapon sniper->nmap"    '[[ "${sn:-0}" -ge 1 ]]'         "${sn:-<none>}"
tw="$(getval tower)";       check "weapon tower->burpsuite" '[[ "${tw:-0}" -ge 1 ]]'        "${tw:-<none>}"
hu="$(getval hunter)";      check "weapon hunter->bloodhound" '[[ "${hu:-0}" -ge 1 ]]'      "${hu:-<none>}"

echo "----------------------------"
if [[ ${fails} -eq 0 ]]; then echo "INTEGRATION TEST PASSED ✔"; exit 0; fi
echo "INTEGRATION TEST FAILED ✘ (${fails} assertion(s) failed)" >&2
exit 1
