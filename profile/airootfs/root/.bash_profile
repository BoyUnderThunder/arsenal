# Arsenal live root profile.
[[ -f ~/.bashrc ]] && . ~/.bashrc

# CI hardening self-test: when booted with `arsenal.selftest` on the kernel
# cmdline (set by tools/integration-test.sh), run the self-test on this console
# so its sentinel is captured over serial. The token is never set on normal
# boots, so this is inert for end users.
if grep -qw arsenal.selftest /proc/cmdline 2>/dev/null; then
    /usr/local/bin/arsenal-selftest || true
fi

# Launch the dark XFCE desktop automatically on the first virtual console only.
# Serial / other VTs drop to a normal shell (so headless boot testing works).
if [[ -z "${DISPLAY:-}" && "${XDG_VTNR:-0}" -eq 1 ]]; then
    exec startx -- -keeptty -nolisten tcp > ~/.xsession-errors 2>&1
fi
