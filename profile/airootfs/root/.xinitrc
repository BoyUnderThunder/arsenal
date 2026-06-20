#!/bin/sh
# Arsenal X session — clean dark XFCE.
export GTK_THEME=Arc-Dark
export QT_STYLE_OVERRIDE=Adwaita-Dark
export XCURSOR_THEME=Adwaita

# Merge X resources if present.
[ -r "$HOME/.Xresources" ] && xrdb -merge "$HOME/.Xresources"

exec startxfce4
