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
    expected="$(curl -fsSL https://blackarch.org/strap.sh.sha1sum 2>/dev/null | awk '{print $1}' || true)"
    if [[ -n "${expected}" ]]; then
        actual="$(sha1sum /tmp/strap.sh | awk '{print $1}')"
        [[ "${expected}" == "${actual}" ]] || c_die "strap.sh checksum mismatch (${actual} != ${expected})"
        c_log "strap.sh checksum verified."
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

c_log "Merging package list (flavor: ${FLAVOR})…"
{
    echo ''
    echo '# ===== Arsenal additions ====='
    grep -vE '^\s*#|^\s*$' "${OVERLAY}/packages.x86_64"
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

# Make sure our scripts are executable inside the image.
chmod 0755 "${PROFILE}/airootfs/usr/local/bin/arsenal"

# -----------------------------------------------------------------------------
# 7. BlackArch repo for the build's pacman
# -----------------------------------------------------------------------------
if ! grep -q '^\[blackarch\]' "${PROFILE}/pacman.conf"; then
    c_log "Adding [blackarch] to the build pacman.conf…"
    cat "${OVERLAY}/pacman-blackarch.conf" >> "${PROFILE}/pacman.conf"
fi

# -----------------------------------------------------------------------------
# 8. Build
# -----------------------------------------------------------------------------
c_log "Running mkarchiso — this pulls many packages and takes a while…"
mkdir -p "${OUT}" "${WORK}/tmp"
mkarchiso -v -w "${WORK}/tmp" -o "${OUT}" "${PROFILE}"

c_log "Build complete:"
ls -lh "${OUT}"/*.iso
