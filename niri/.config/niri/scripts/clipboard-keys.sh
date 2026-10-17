#!/usr/bin/env sh
# Mac-style Cmd+C / Cmd+X / Cmd+V (niri binds, docs/niri.md): type the focused app's own
# copy/cut/paste/select-all keys through wtype.
# Usage: clipboard-keys.sh copy|cut|paste|select
#
# Keys per app (the app's own standard keys; see docs/niri.md for what was tested):
#   GUI apps (GTK, Firefox, Strata): Ctrl+C / Ctrl+X / Ctrl+V / Ctrl+A
#   Zed: Ctrl+Insert / Shift+Delete / Shift+Insert (vim mode owns Ctrl+C/X/V/A); select
#     all is Ctrl+Alt+Shift+A, bound to editor::SelectAll in ~/.config/zed/keymap.json
#   terminals (Ghostty, Herdr UI): Ctrl+Shift+C / V / A, so Ctrl+C keeps interrupting
#     the running program; "cut" copies.
set -eu

app="$(niri msg --json focused-window | sed -n 's/.*"app_id":"\([^"]*\)".*/\1/p')"

case "$app" in
  com.mitchellh.ghostty|so.pen.herdr-gpui) kind=term ;;
  dev.zed.Zed*) kind=zed ;;
  *) kind=gui ;;
esac

case "$1:$kind" in
  copy:term|cut:term) exec wtype -M ctrl -M shift c -m shift -m ctrl ;;
  paste:term) exec wtype -M ctrl -M shift v -m shift -m ctrl ;;
  select:term) exec wtype -M ctrl -M shift a -m shift -m ctrl ;;
  copy:zed) exec wtype -M ctrl -k Insert -m ctrl ;;
  cut:zed) exec wtype -M shift -k Delete -m shift ;;
  paste:zed) exec wtype -M shift -k Insert -m shift ;;
  select:zed) exec wtype -M ctrl -M alt -M shift a -m shift -m alt -m ctrl ;;
  copy:gui) exec wtype -M ctrl c -m ctrl ;;
  cut:gui) exec wtype -M ctrl x -m ctrl ;;
  paste:gui) exec wtype -M ctrl v -m ctrl ;;
  select:gui) exec wtype -M ctrl a -m ctrl ;;
  *) echo "usage: $0 copy|cut|paste|select" >&2; exit 2 ;;
esac
