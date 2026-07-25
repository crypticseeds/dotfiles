#!/bin/sh
# Self-healing launcher for the herdr-file-viewer plugin.
#
# herdr registers plugins per session (~/.config/herdr/sessions/<name>/plugins.json),
# so a plugin installed in one named session is invisible to the others. This script
# keeps ONE shared checkout and links it into the current session on first use, so
# the prefix+f keybindings in config.toml work in every session, current or future.
#
# Usage: file-viewer-open.sh [open-file-viewer|open-file-viewer-tab]
set -u

action="${1:-open-file-viewer}"
herdr="${HERDR_BIN_PATH:-herdr}"
root="$HOME/.local/share/herdr-plugins/herdr-file-viewer"
repo="https://github.com/smarzban/herdr-file-viewer"

# One-time per machine: fetch the plugin source.
if [ ! -d "$root/.git" ]; then
  mkdir -p "${root%/*}"
  git clone --quiet "$repo" "$root" || exit 1
fi

# One-time per machine: fetch or build the binary (herdr plugin link skips build steps).
if [ ! -x "$root/target/release/herdr-file-viewer" ]; then
  (cd "$root" && sh scripts/fetch-or-build.sh) || exit 1
fi

# One-time per session: register the shared checkout in this session's registry.
if ! "$herdr" plugin list --json 2>/dev/null | grep -q '"herdr-file-viewer"'; then
  "$herdr" plugin link "$root" || exit 1
fi

exec "$herdr" plugin action invoke "$action" --plugin herdr-file-viewer
