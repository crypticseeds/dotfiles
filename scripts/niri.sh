#!/usr/bin/env sh
# Installs everything the niri desktop needs on Fedora (docs/niri.md):
#   1. packages/niri.txt (+ the ghostty COPR),
#   2. per-user apps the niri binds launch: Zed, Strata, Herdr UI,
#   3. icon theme and the wallpaper folder Noctalia is pointed at.
# The configs themselves (niri, ghostty, noctalia) are stowed by `make niri`.
# Idempotent: re-running only installs what is missing.
set -eu
cd "$(dirname "$0")/.."

BIN="$HOME/.local/bin"
mkdir -p "$BIN"
PATH="$BIN:$PATH" # binaries installed below must be visible to the checks below

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

. /etc/os-release
[ "$ID" = fedora ] || { echo "niri setup supports Fedora only (found $ID)" >&2; exit 1; }

# --- Packages ----------------------------------------------------------------
say "packages (packages/niri.txt)"
sudo dnf install -y dnf5-plugins
sudo dnf -y copr enable scottames/ghostty
grep -vE '^\s*(#|$)' packages/niri.txt | xargs sudo dnf install -y

for p in mako dunst swaync; do
  if rpm -q "$p" >/dev/null 2>&1; then
    echo "WARN: $p competes with Noctalia for notifications; remove it: sudo dnf remove $p" >&2
  fi
done

# --- Zed (Mod+Z) ---------------------------------------------------------------
if ! have zed; then
  say "zed: official installer -> ~/.local"
  curl -fsSL https://zed.dev/install.sh | sh
fi

# --- Strata (Mod+E) ------------------------------------------------------------
# Strata's own install.sh only installs unattended on Arch, so follow its README's manual
# install: checksum-verified release archive, binary in ~/.local/bin, desktop entry + icon.
install_strata() {
  case "$(uname -m)" in
    x86_64) target=x86_64-unknown-linux-gnu ;;
    aarch64) target=aarch64-unknown-linux-gnu ;;
    *) echo "WARN: strata has no release for $(uname -m); skipped" >&2; return 0 ;;
  esac
  tag="$(curl -fsSL https://api.github.com/repos/lgse/strata/releases/latest | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p')"
  archive="strata-${tag#v}-$target.tar.gz"
  url="https://github.com/lgse/strata/releases/download/$tag"
  say "strata $tag: release archive -> ~/.local/bin"
  tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/$archive" "$url/$archive"
  curl -fsSL -o "$tmp/$archive.sha256" "$url/$archive.sha256"
  (cd "$tmp" && sha256sum --check --quiet "$archive.sha256" && tar -xzf "$archive")
  dir="$tmp/${archive%.tar.gz}"
  install -Dm755 "$dir/strata" "$BIN/strata"
  install -Dm644 "$dir/io.github.lgse.Strata.svg" \
    "$HOME/.local/share/icons/hicolor/scalable/apps/io.github.lgse.Strata.svg"
  mkdir -p "$HOME/.local/share/applications"
  sed "s|^Exec=strata |Exec=$BIN/strata |" "$dir/io.github.lgse.Strata.desktop" \
    >"$HOME/.local/share/applications/io.github.lgse.Strata.desktop"
  update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
  gtk-update-icon-cache -qtf "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
  rm -rf "$tmp"
}
have strata || install_strata

# --- Herdr UI (Mod+A) ----------------------------------------------------------
# A client for the herdr daemon (packages/harnesses.sh installs herdr itself).
if ! have herdr-gpui; then
  if have herdr; then
    say "herdr-gpui: official installer (dnf)"
    curl -fsSL https://herdrui.dev/install.sh | sh
  else
    echo "WARN: herdr-gpui skipped: install herdr first (sh packages/harnesses.sh)" >&2
  fi
fi

# --- Look ----------------------------------------------------------------------
gsettings set org.gnome.desktop.interface icon-theme Papirus-Dark
mkdir -p "$HOME/Pictures/Wallpapers"

say "niri desktop installed. Log out, pick Niri from the gear on the login screen."
