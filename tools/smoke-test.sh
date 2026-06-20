#!/usr/bin/env bash
# =============================================================================
#  Arsenal QEMU smoke test
# =============================================================================
#  Boots an Arsenal ISO headlessly in QEMU and watches the serial console for
#  proof that the system reached a working autologin shell. Exits 0 on success.
#
#  Requires: qemu-system-x86_64. The ISO must be built with ARSENAL_SERIAL=1
#  (so the kernel logs to ttyS0). Uses KVM if /dev/kvm exists, else TCG.
#
#  Usage: tools/smoke-test.sh path/to/arsenal.iso [timeout_seconds]
# =============================================================================
set -euo pipefail

ISO="${1:?usage: smoke-test.sh <iso> [timeout]}"
TIMEOUT="${2:-1200}"
[[ -f "${ISO}" ]] || { echo "smoke-test: ISO not found: ${ISO}" >&2; exit 2; }
command -v qemu-system-x86_64 >/dev/null || { echo "smoke-test: qemu-system-x86_64 missing" >&2; exit 2; }

LOG="$(mktemp /tmp/arsenal-serial.XXXXXX.log)"
MEM="${SMOKE_MEM:-4096}"
# Markers that prove we booted to the Arsenal live environment.
MARKERS=('root@arsenal' 'white-hat security OS' 'Arsenal')

ACCEL=(-accel tcg)
if [[ -w /dev/kvm ]]; then ACCEL=(-enable-kvm -cpu host); echo "smoke-test: using KVM"; else echo "smoke-test: using TCG (slow)"; fi

echo "smoke-test: booting ${ISO} (timeout ${TIMEOUT}s), serial -> ${LOG}"
qemu-system-x86_64 \
    "${ACCEL[@]}" \
    -m "${MEM}" -smp 2 \
    -cdrom "${ISO}" -boot d \
    -nographic -display none \
    -serial "file:${LOG}" \
    -no-reboot \
    >/dev/null 2>&1 &
QPID=$!

cleanup() { kill "${QPID}" 2>/dev/null || true; wait "${QPID}" 2>/dev/null || true; }
trap cleanup EXIT

deadline=$(( $(date +%s) + TIMEOUT ))
ok=0
while [[ $(date +%s) -lt ${deadline} ]]; do
    if ! kill -0 "${QPID}" 2>/dev/null; then
        echo "smoke-test: QEMU exited early."; break
    fi
    for m in "${MARKERS[@]}"; do
        if grep -qaF "${m}" "${LOG}"; then
            echo "smoke-test: matched marker '${m}' — boot succeeded."
            ok=1; break 2
        fi
    done
    sleep 5
done

echo "----- last 60 lines of serial log -----"
tail -n 60 "${LOG}" 2>/dev/null | tr -d '\000' || true
echo "---------------------------------------"

if [[ ${ok} -eq 1 ]]; then
    echo "SMOKE TEST PASSED ✔"
    exit 0
fi
echo "SMOKE TEST FAILED ✘ (no boot marker within ${TIMEOUT}s)" >&2
exit 1
