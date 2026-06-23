# Arsenal live root profile.
[[ -f ~/.bashrc ]] && . ~/.bashrc

# Launch the dark XFCE desktop automatically on the first virtual console only.
# Serial / other VTs drop to a normal shell (so headless boot testing works).
if [[ -z "${DISPLAY:-}" && "${XDG_VTNR:-0}" -eq 1 ]]; then
    exec startx -- -keeptty -nolisten tcp > ~/.xsession-errors 2>&1
fi
