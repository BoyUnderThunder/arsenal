#!/usr/bin/env bash
# =============================================================================
#  Arsenal release verifier
# =============================================================================
#  Verifies a downloaded Arsenal GitHub release end-to-end:
#    1. the SHA256SUMS manifest (split parts + provenance files),
#    2. the detached GPG signature over SHA256SUMS (when present + gpg is set up),
#    3. reassembles the split ISO and verifies the whole-image checksum.
#
#  Only present files are checked, so it works whether you grabbed just the ISO
#  parts or the full set (parts + SBOMs + signature).
#
#  Usage: tools/verify-release.sh [DIR]     (DIR defaults to the current dir)
#  Needs: sha256sum (coreutils); gpg only for the signature check. No root.
# =============================================================================
set -euo pipefail

DIR="${1:-.}"
cd "${DIR}" || { echo "verify-release: cannot cd to '${DIR}'" >&2; exit 2; }
command -v sha256sum >/dev/null || { echo "verify-release: sha256sum not found (install coreutils)" >&2; exit 2; }

pass() { printf '  [PASS] %s\n' "$*"; }
warn() { printf '  [WARN] %s\n' "$*"; }
fail() { printf '  [FAIL] %s\n' "$*"; }

fails=0
checks=0

# --- Discover the ISO base name (arsenal-<ver>-x86_64.iso) --------------------
BASE=""
for f in *.iso.sha256; do [[ -e "$f" ]] && { BASE="${f%.sha256}"; break; }; done
[[ -z "${BASE}" ]] && for f in *.iso.part00; do [[ -e "$f" ]] && { BASE="${f%.part00}"; break; }; done
[[ -z "${BASE}" ]] && for f in *.iso; do [[ -e "$f" ]] && { BASE="$f"; break; }; done
[[ -n "${BASE}" ]] || { echo "verify-release: no Arsenal release files found in $(pwd)" >&2; exit 2; }
echo "Verifying release: ${BASE}"
echo

# --- 1. SHA256SUMS manifest (parts + provenance) -----------------------------
if [[ -f SHA256SUMS ]]; then
    checks=$((checks + 1))
    out="$(sha256sum -c --ignore-missing SHA256SUMS 2>/dev/null || true)"
    if grep -q ': FAILED' <<<"${out}"; then
        fail "SHA256SUMS: checksum mismatch"
        grep ': FAILED' <<<"${out}" | sed 's/^/        /'
        fails=$((fails + 1))
    elif grep -q ': OK$' <<<"${out}"; then
        pass "SHA256SUMS: $(grep -c ': OK$' <<<"${out}") file(s) match"
    else
        warn "SHA256SUMS: none of its listed files are present here"
    fi
else
    warn "SHA256SUMS not present — skipping manifest check"
fi

# --- 2. GPG signature over SHA256SUMS ----------------------------------------
if [[ -f SHA256SUMS.asc && -f SHA256SUMS ]]; then
    if command -v gpg >/dev/null; then
        checks=$((checks + 1))
        if gpg --verify SHA256SUMS.asc SHA256SUMS >/dev/null 2>&1; then
            pass "GPG signature on SHA256SUMS is valid"
        else
            fail "GPG signature invalid or the signer's public key is not imported"
            echo "        import the Arsenal public key, then re-run (or: gpg --verify SHA256SUMS.asc SHA256SUMS)"
            fails=$((fails + 1))
        fi
    else
        warn "SHA256SUMS.asc present but gpg is not installed — skipping signature check"
    fi
else
    warn "no valid signature pair (SHA256SUMS.asc) — release is unsigned or the signature was not downloaded"
fi

# --- 3. Reassemble the ISO from parts, verify the whole-image checksum --------
shopt -s nullglob
parts=( "${BASE}".part* )
shopt -u nullglob
if ((${#parts[@]})) && [[ ! -f "${BASE}" ]]; then
    echo "Reassembling ${BASE} from ${#parts[@]} part(s)…"
    cat "${parts[@]}" > "${BASE}"
fi

if [[ -f "${BASE}.sha256" ]]; then
    if [[ -f "${BASE}" ]]; then
        checks=$((checks + 1))
        if sha256sum -c --quiet "${BASE}.sha256" >/dev/null 2>&1; then
            pass "${BASE}: image checksum matches"
        else
            fail "${BASE}: image checksum MISMATCH — do not use this ISO"
            fails=$((fails + 1))
        fi
    else
        warn "${BASE}.sha256 present but no ISO or parts to verify against"
    fi
fi

echo
if ((checks == 0)); then
    echo "verify-release: nothing to verify (no SHA256SUMS or *.iso.sha256 found)" >&2
    exit 2
fi
if ((fails == 0)); then
    echo "RELEASE VERIFIED ✔  (${checks} check(s) passed)"
    exit 0
fi
echo "RELEASE VERIFICATION FAILED ✘  (${fails} of ${checks} check(s) failed)" >&2
exit 1
