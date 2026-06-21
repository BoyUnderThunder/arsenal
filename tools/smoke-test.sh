#!/usr/bin/env bash
# =============================================================================
#  Arsenal QEMU smoke test
# =============================================================================
#  Boots an Arsenal ISO headlessly in QEMU and confirms it reaches the autologin
#  root shell (not just the boot menu). Uses a *direct kernel boot*
#  (-kernel/-initrd) with a forced serial console, so the boot is observable
#  regardless of the ISO's own console settings, with the ISO attached as a CD
#  so the archiso initramfs finds the squashfs by label.
#
#  Must run as root (it loop-mounts the ISO to extract the kernel/initramfs).
#  Uses KVM if /dev/kvm is available, else TCG.
#
#  Usage: sudo tools/smoke-test.sh path/to/arsenal.iso [timeout_seconds]
# =============================================================================
set -euo pipefail

ISO="${1:?usage: smoke-test.sh <iso> [timeout]}"
TIMEOUT="${2:-900}"
[[ -f "${ISO}" ]] || { echo "smoke-test: ISO not found: ${ISO}" >&2; exit 2; }
command -v qemu-system-x86_64 >/dev/null || { echo "smoke-test: qemu-system-x86_64 missing" >&2; exit 2; }
[[ ${EUID} -eq 0 ]] || { echo "smoke-test: must run as root (mounts the ISO)" >&2; exit 2; }

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

# Markers that only appear AFTER the system reaches its autologin shell.
MARKERS='root@arsenal|BlackArch-powered|hostname=arsenal'
FAIL_RE='Kernel panic|Unable to mount root|Attempted to kill init|Cannot open root|Entering emergency|You are in emergency'

# --- Extract kernel + initramfs (+ microcode) from the ISO --------------------
LABEL="$(blkid -o value -s LABEL "${ISO}" 2>/dev/null || echo '')"
mount -o loop,ro "${ISO}" "${MNT}"
VMLINUZ="$(find "${MNT}" -name 'vmlinuz-linux-hardened' | head -1)"
INITRD="$(find "${MNT}" -name 'initramfs-linux-hardened.img' | head -1)"
UCODE="$(find "${MNT}" -name '*-ucode.img' | sort | tr '\n' ' ')"
[[ -n "${VMLINUZ}" && -n "${INITRD}" ]] || { echo "smoke-test: kernel/initramfs not found on ISO" >&2; exit 2; }
# install_dir = first path component under the mountpoint (e.g. "arsenal")
BASEDIR="${VMLINUZ#"${MNT}"/}"; BASEDIR="${BASEDIR%%/*}"
cp "${VMLINUZ}" "${WORK}/vmlinuz"
# shellcheck disable=SC2086
cat ${UCODE} "${INITRD}" > "${WORK}/initrd.img"
umount "${MNT}"

ACCEL=(-accel tcg)
if [[ -w /dev/kvm ]]; then ACCEL=(-enable-kvm -cpu host); echo "smoke-test: using KVM"; else echo "smoke-test: using TCG (slow)"; fi

echo "smoke-test: booting ${ISO} (label=${LABEL}, basedir=${BASEDIR}, timeout ${TIMEOUT}s)"
# Serial -> qemu stdout -> shell redirect (qemu never opens the log itself).
qemu-system-x86_64 "${ACCEL[@]}" -m "${MEM}" -smp 2 \
    -kernel "${WORK}/vmlinuz" -initrd "${WORK}/initrd.img" \
    -append "archisobasedir=${BASEDIR} archisolabel=${LABEL} console=ttyS0,115200 cow_spacesize=1G" \
    -cdrom "${ISO}" -display none -serial stdio -monitor none -no-reboot > "${LOG}" 2>&1 &
QPID=$!

ok=0
deadline=$(( $(date +%s) + TIMEOUT ))
while [[ $(date +%s) -lt ${deadline} ]]; do
    kill -0 "${QPID}" 2>/dev/null || { echo "smoke-test: QEMU exited early"; break; }
    if grep -qaE "${MARKERS}" "${LOG}"; then ok=1; echo "smoke-test: reached autologin root shell"; break; fi
    if grep -qaiE "${FAIL_RE}" "${LOG}"; then echo "smoke-test: boot-failure signature on serial"; break; fi
    sleep 5
done

echo "----- serial log (tail 60) -----"
tail -n 60 "${LOG}" 2>/dev/null | tr -d '\000' || true
echo "--------------------------------"

if [[ ${ok} -eq 1 ]]; then echo "SMOKE TEST PASSED ✔"; exit 0; fi
echo "SMOKE TEST FAILED ✘ (no autologin shell within ${TIMEOUT}s)" >&2
exit 1
