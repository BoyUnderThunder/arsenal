#!/usr/bin/env bash
# =============================================================================
#  Arsenal ISO builder
# =============================================================================
#  Assembles an archiso profile from the system "releng" base + the Arsenal
#  overlay, wires in the BlackArch repository (via strap.sh), switches to the
#  linux-hardened kernel, applies Arsenal branding, and runs mkarchiso.
#
#  Run as root on Arch Linux, or inside an `archlinux` container (see the
#  GitHub Actions workflow / README). On non-Arch hosts use those paths.
#
#  Env knobs:
#    ARSENAL_PROFILE=full|lean   package flavor (default: full)
#    ARSENAL_SERIAL=1            add a serial console to boot cmdline (CI smoke)
#    ARSENAL_WORK=<dir>          mkarchiso work dir (default: ./work)
#    ARSENAL_OUT=<dir>           ISO output dir (default: ./out)
#    SKIP_STRAP=1               assume BlackArch repo is already configured
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OVERLAY="${HERE}/profile"
WORK="${ARSENAL_WORK:-${HERE}/work}"
OUT="${ARSENAL_OUT:-${HERE}/out}"
PROFILE="${WORK}/arsenal-profile"
RELENG="/usr/share/archiso/configs/releng"
FLAVOR="${ARSENAL_PROFILE:-full}"

c_log() { printf '\033[1;31m[arsenal]\033[0m %s\n' "$*"; }
c_die() { printf '\033[1;31m[arsenal:ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

[[ ${EUID} -eq 0 ]] || c_die "must run as root (mkarchiso requires it)."
command -v pacman >/dev/null 2>&1 || c_die "pacman not found — build on Arch Linux or in an archlinux container."

# -----------------------------------------------------------------------------
# 1. Build dependencies
# -----------------------------------------------------------------------------
c_log "Installing build dependencies (archiso, git, curl)…"
pacman -Sy --needed --noconfirm archlinux-keyring
pacman -S  --needed --noconfirm archiso git curl

[[ -d ${RELENG} ]] || c_die "releng profile missing at ${RELENG} (is 'archiso' installed?)"

# -----------------------------------------------------------------------------
# 2. BlackArch repository via strap.sh
# -----------------------------------------------------------------------------
if [[ "${SKIP_STRAP:-0}" != "1" ]] && ! grep -q '^\[blackarch\]' /etc/pacman.conf; then
    c_log "Bootstrapping BlackArch with strap.sh…"
    curl -fsSL https://blackarch.org/strap.sh -o /tmp/strap.sh
    # BlackArch's server returns its homepage (HTTP 200) for missing paths, so a
    # bad download looks like success. Verify we actually got a shell script.
    if ! head -n1 /tmp/strap.sh | grep -q '^#!'; then
        c_die "downloaded strap.sh is not a shell script — BlackArch unreachable or URL changed."
    fi
    chmod +x /tmp/strap.sh
    /tmp/strap.sh
fi
pacman -Sy

# -----------------------------------------------------------------------------
# 3. Assemble profile: releng base + Arsenal overlay
# -----------------------------------------------------------------------------
c_log "Assembling profile at ${PROFILE} …"
rm -rf "${PROFILE}"
mkdir -p "${PROFILE}"
cp -a "${RELENG}/." "${PROFILE}/"
cp -a "${OVERLAY}/airootfs/." "${PROFILE}/airootfs/"

# Install the Arsenal platform CLI (Python) into the image and stamp the build.
c_log "Installing Arsenal platform CLI…"
install -d "${PROFILE}/airootfs/usr/lib/arsenal"
cp -a "${HERE}/cli/arsenal_cli" "${PROFILE}/airootfs/usr/lib/arsenal/"
find "${PROFILE}/airootfs/usr/lib/arsenal" -name '__pycache__' -type d -prune -exec rm -rf {} +
if [[ -f "${PROFILE}/airootfs/etc/arsenal/arsenal.conf" ]]; then
    sed -i "s/^build_date *=.*/build_date = $(date +%Y.%m.%d)/" "${PROFILE}/airootfs/etc/arsenal/arsenal.conf"
fi

c_log "Merging package list (flavor: ${FLAVOR})…"
{
    echo ''
    echo '# ===== Arsenal additions ====='
    # Strip inline "# comment" docs, trailing whitespace, and blank lines so the
    # profile's packages.x86_64 contains bare package names only.
    sed -e 's/#.*//' -e 's/[[:space:]]\+$//' -e '/^[[:space:]]*$/d' "${OVERLAY}/packages.x86_64"
} >> "${PROFILE}/packages.x86_64"

if [[ "${FLAVOR}" == "lean" ]]; then
    c_log "Lean flavor: dropping heavy packages…"
    while read -r p; do
        [[ -z "${p}" || "${p}" == \#* ]] && continue
        sed -i "\#^${p}\$#d" "${PROFILE}/packages.x86_64"
    done < "${OVERLAY}/packages.lean.drop"
fi

# -----------------------------------------------------------------------------
# 4. Switch to the linux-hardened kernel
# -----------------------------------------------------------------------------
c_log "Switching to the linux-hardened kernel…"
sed -i '/^linux$/d' "${PROFILE}/packages.x86_64"   # drop stock kernel (hardened is in additions)
rm -f "${PROFILE}/airootfs/etc/mkinitcpio.d/linux.preset"

# Point all boot loaders at the hardened kernel + initramfs.
mapfile -d '' BOOTCFG < <(find "${PROFILE}/syslinux" "${PROFILE}/efiboot" "${PROFILE}/grub" -type f -print0 2>/dev/null)
if ((${#BOOTCFG[@]})); then
    sed -i \
        -e 's/vmlinuz-linux\b/vmlinuz-linux-hardened/g' \
        -e 's/initramfs-linux\.img/initramfs-linux-hardened.img/g' \
        -e 's/initramfs-linux-fallback\.img/initramfs-linux-hardened-fallback.img/g' \
        "${BOOTCFG[@]}"
fi

# -----------------------------------------------------------------------------
# 5. Kernel cmdline: AppArmor (+ optional serial console for headless testing)
# -----------------------------------------------------------------------------
EXTRA_CMDLINE="apparmor=1 security=apparmor lsm=landlock,lockdown,yama,integrity,apparmor,bpf"
[[ "${ARSENAL_SERIAL:-0}" == "1" ]] && EXTRA_CMDLINE+=" console=tty0 console=ttyS0,115200"
c_log "Injecting kernel cmdline: ${EXTRA_CMDLINE}"
if ((${#BOOTCFG[@]})); then
    sed -i "s#archisolabel=%ARCHISO_LABEL%#archisolabel=%ARCHISO_LABEL% ${EXTRA_CMDLINE}#g" "${BOOTCFG[@]}"
fi

# -----------------------------------------------------------------------------
# 6. Branding
# -----------------------------------------------------------------------------
c_log "Applying Arsenal branding…"
sed -i \
    -e 's/^iso_name=.*/iso_name="arsenal"/' \
    -e 's/^iso_label=.*/iso_label="ARSENAL_$(date +%Y%m)"/' \
    -e 's#^iso_publisher=.*#iso_publisher="Arsenal Project <https://github.com/BoyUnderThunder/arsenal>"#' \
    -e 's#^iso_application=.*#iso_application="Arsenal - White-Hat Security OS"#' \
    -e 's/^install_dir=.*/install_dir="arsenal"/' \
    "${PROFILE}/profiledef.sh"

# Boot-menu titles: "Arch Linux" -> "Arsenal"
if ((${#BOOTCFG[@]})); then
    sed -i 's/Arch Linux/Arsenal/g' "${BOOTCFG[@]}"
fi

# Make sure our scripts are executable inside the image. The exec bit can be
# dropped in transit through CI/container copies, so set it explicitly here —
# without this the boot-time self-test hook hits "permission denied".
chmod 0755 "${PROFILE}/airootfs/usr/local/bin/arsenal" \
           "${PROFILE}/airootfs/usr/local/bin/arsenal-selftest"

# -----------------------------------------------------------------------------
# 7. BlackArch repo for the build's pacman
# -----------------------------------------------------------------------------
if ! grep -q '^\[blackarch\]' "${PROFILE}/pacman.conf"; then
    c_log "Adding [blackarch] to the build pacman.conf…"
    cat "${OVERLAY}/pacman-blackarch.conf" >> "${PROFILE}/pacman.conf"
fi

# -----------------------------------------------------------------------------
# 8. Validate every package name resolves (fast — before the expensive build)
# -----------------------------------------------------------------------------
c_log "Validating that every package resolves against the repos…"
mapfile -t PKGS < <(sed -e 's/#.*//' -e 's/[[:space:]]\+$//' -e '/^[[:space:]]*$/d' "${PROFILE}/packages.x86_64")
# pacman prints the offending package name(s) AND any dependency breakage to
# stdout, not stderr — so capture both streams or the cause is lost.
if ! pacman -Sp --noconfirm "${PKGS[@]}" >/tmp/arsenal-resolve.err 2>&1; then
    c_log "Package resolution failed — pacman output:"
    grep -iE 'target not found|could not find|could not satisfy|unable to satisfy|breaks dependency|requires|conflicting' /tmp/arsenal-resolve.err >&2 || true
    echo "----- full pacman resolve log -----" >&2
    cat /tmp/arsenal-resolve.err >&2
    c_die "fix the offending names in profile/packages.x86_64 and rebuild."
fi
c_log "All $(printf '%s\n' "${PKGS[@]}" | wc -l) package entries resolve."

# -----------------------------------------------------------------------------
# 9. Build
# -----------------------------------------------------------------------------
c_log "Running mkarchiso — this pulls many packages and takes a while…"
mkdir -p "${OUT}" "${WORK}/tmp"
mkarchiso -v -w "${WORK}/tmp" -o "${OUT}" "${PROFILE}"

c_log "Build complete:"
ls -lh "${OUT}"/*.iso
