#!/usr/bin/env bash
# =============================================================================
#  Arsenal preflight — run the fast checks CI runs, locally, before you push.
# =============================================================================
#  Mirrors ci-test.yml: ruff lint, the CLI unit tests, the SBOM generator
#  tests, and ShellCheck. A check is skipped (with a note) if its tool isn't
#  installed; the script exits non-zero if any check that ran did not pass.
#  It does NOT build the ISO (that needs Arch + network; see build.sh).
#
#  Usage: tools/preflight.sh        (from anywhere in the repo)
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${HERE}" || { echo "preflight: cannot cd to repo root ${HERE}" >&2; exit 2; }

rc=0
step() {  # step "name" cmd args...
    local name="$1"; shift
    printf '\n==> %s\n' "${name}"
    if "$@"; then
        printf '  [PASS] %s\n' "${name}"
    else
        printf '  [FAIL] %s\n' "${name}"; rc=1
    fi
}
skip() { printf '\n==> %s — SKIPPED (%s not installed)\n' "$1" "$2"; }

if command -v ruff >/dev/null 2>&1; then
    step "ruff lint" ruff check --config cli/pyproject.toml cli tools
else
    skip "ruff lint" ruff
fi

step "CLI unit tests" bash -c 'cd cli && python -m unittest discover -s tests -t . -q'
step "tools tests (SBOM gen + verify)" bash -c 'cd tools && python -m unittest discover -s . -p "test_*.py" -q'

if command -v shellcheck >/dev/null 2>&1; then
    step "ShellCheck" shellcheck -S warning \
        profile/airootfs/usr/local/bin/arsenal \
        profile/airootfs/usr/local/bin/arsenal-selftest \
        profile/airootfs/etc/profile.d/zz-arsenal-selftest.sh \
        tools/smoke-test.sh tools/integration-test.sh tools/verify-release.sh \
        tools/preflight.sh build.sh
else
    skip "ShellCheck" shellcheck
fi

echo
if [[ ${rc} -eq 0 ]]; then
    echo "PREFLIGHT OK ✔"
else
    echo "PREFLIGHT FAILED ✘ — fix the above before pushing" >&2
fi
exit ${rc}
