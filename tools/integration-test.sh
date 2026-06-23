#!/usr/bin/env bash
# =============================================================================
#  Arsenal post-boot integration test
# =============================================================================
#  Goes beyond smoke-test.sh ("does it reach a shell?") and proves the Fortress
#  is actually LIVE. Boots the ISO headless via a direct kernel boot (with the
#  REAL Arsenal kernel cmdline, incl. the AppArmor LSM params, plus the
#  `arsenalselftest` token). A login-shell hook (/etc/profile.d) sees that token
#  on the serial autologin shell and runs /usr/local/bin/arsenal-selftest, which
#  prints the assertions and a sentinel to the serial console:
#
#    * linux-hardened kernel running
#    * key sysctls applied (kptr_restrict, ptrace_scope, bpf_jit_harden)
#    * nftables input policy drop
#    * AppArmor module loaded + apparmor.service active
#    * arsenal doctor exits 0
#    * sample weapons resolve (sniper/tower/hunter)
#
#  Passes only on `ARSENAL-SELFTEST: PASS`; fails on `... FAIL`, a boot-failure
#  signature, or timeout. Uses the same proven capture path as smoke-test.sh
#  (serial -> stdout -> log), so it is robust in CI.
#
#  Must run as root (loop-mounts the ISO). Uses KVM if available, else TCG.
#  Usage: sudo tools/integration-test.sh path/to/arsenal.iso [timeout_seconds]
# =============================================================================
set -euo pipefail

ISO="${1:?usage: integration-test.sh <iso> [timeout]}"
TIMEOUT="${2:-1200}"
[[ -f "${ISO}" ]] || { echo "integration-test: ISO not found: ${ISO}" >&2; exit 2; }
command -v qemu-system-x86_64 >/dev/null || { echo "integration-test: qemu-system-x86_64 missing" >&2; exit 2; }
[[ ${EUID} -eq 0 ]] || { echo "integration-test: must run as root (mounts the ISO)" >&2; exit 2; }

MEM="${SMOKE_MEM:-4096}"
WORK="$(mktemp -d)"
LOG="${WORK}/serial.log"
MNT="${WORK}/mnt"; mkdir -p "${MNT}"
QPID=""

cleanup() {
    [[ -n "${QPID}" ]] && kill "${QPID}" 2>/dev/null || true
    mountpoint -q "${MNT}" && umount "${MNT}" 2>/dev/null || true
    rm -rf "${WORK}" 2>/dev/null || true
}
trap cleanup EXIT

PASS_RE='ARSENAL-SELFTEST: PASS'
FAILMARK='ARSENAL-SELFTEST: FAIL'
BOOT_FAIL_RE='Kernel panic|Unable to mount root|Attempted to kill init|Cannot open root|Entering emergency|You are in emergency'

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

# Boot with the REAL Arsenal cmdline (so AppArmor is actually enabled, exactly
# as the ISO's bootloader configures it) plus the self-test token.
APPEND="archisobasedir=${BASEDIR} archisolabel=${LABEL}"
APPEND+=" apparmor=1 security=apparmor lsm=landlock,lockdown,yama,integrity,apparmor,bpf"
APPEND+=" console=ttyS0,115200 cow_spacesize=1G arsenalselftest"

echo "integration-test: booting ${ISO} (label=${LABEL}, basedir=${BASEDIR}, timeout ${TIMEOUT}s)"
qemu-system-x86_64 "${ACCEL[@]}" -m "${MEM}" -smp 2 \
    -kernel "${WORK}/vmlinuz" -initrd "${WORK}/initrd.img" \
    -append "${APPEND}" \
    -cdrom "${ISO}" -display none -serial stdio -monitor none -no-reboot > "${LOG}" 2>&1 &
QPID=$!

ok=0
deadline=$(( $(date +%s) + TIMEOUT ))
while [[ $(date +%s) -lt ${deadline} ]]; do
    kill -0 "${QPID}" 2>/dev/null || { echo "integration-test: QEMU exited early"; break; }
    if grep -qaE "${PASS_RE}" "${LOG}"; then ok=1; break; fi
    if grep -qaF "${FAILMARK}" "${LOG}"; then echo "integration-test: self-test reported FAIL"; break; fi
    if grep -qaiE "${BOOT_FAIL_RE}" "${LOG}"; then echo "integration-test: boot-failure signature on serial"; break; fi
    sleep 5
done

# Preserve the serial log outside the temp dir so CI can upload it on failure.
cp "${LOG}" /tmp/arsenal-serial-integration.log 2>/dev/null || true

echo "----- self-test output -----"
grep -aE '^\[(PASS|FAIL|INFO)\]|^ARSENAL-SELFTEST:' "${LOG}" | tr -d '\000\r' || true
if grep -qa 'arsenal login' "${LOG}"; then
    echo "diag: autologin reached (boot OK)"
else
    echo "diag: autologin NOT reached — boot/console problem"
fi
echo "diag: serial log is $(wc -l < "${LOG}" 2>/dev/null || echo '?') line(s)"
echo "----- serial log (tail 120) -----"
tail -n 120 "${LOG}" 2>/dev/null | tr -d '\000\r' || true
echo "--------------------------------"

if [[ ${ok} -eq 1 ]]; then echo "INTEGRATION TEST PASSED ✔"; exit 0; fi
echo "INTEGRATION TEST FAILED ✘" >&2
exit 1
