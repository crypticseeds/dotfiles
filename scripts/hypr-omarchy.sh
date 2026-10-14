#!/usr/bin/env bash
# Set up the Omarchy-style Hyprland session beside the regular one (Fedora; `make hypr-omarchy`).
# Idempotent, no sudo: it never overwrites a file you changed. It
#   1. checks the tools the session needs and prints the dnf command for missing ones,
#   2. checks out Omarchy at a pinned commit into ~/.local/share/omarchy ($OMARCHY_PATH),
#   3. seeds ~/.config/omarchy/shell.json (bar, dock pins, disabled plugins),
#   4. points xdg-terminal-exec at WezTerm for Hyprland sessions,
#   5. generates the theme for Hyprland and the shell (no other app is touched),
#   6. installs JetBrainsMono Nerd Font and Omarchy's icon font into ~/.local/share/fonts,
#   7. installs the Strata file manager (verified release) into ~/.local/bin.
# The config itself (~/.config/hypr-omarchy, ~/.local/bin/hypr-omarchy) is stowed by the
# make target. Start the session from a TTY with `hypr-omarchy`.
set -euo pipefail

OMARCHY_REPO=https://github.com/omacom/omarchy
OMARCHY_REF=256e05bd0b25486313f1ee978ff43e62eddf4091 # branch quattro, 2026-10-14
NERD_FONTS_VERSION=v3.5.1
STRATA_VERSION=1.0.0 # first install only; Strata updates itself (Settings -> Updates)
# Our dark gruvbox (scripts/hypr-omarchy/themes/), built on Omarchy's gruvbox.
# Any Omarchy theme name works too, e.g. THEME=kanagawa make hypr-omarchy (first setup only).
THEME="${THEME:-gruvbox-hard-seeds}"
THEME_BASE=gruvbox

here="$(cd "$(dirname "$0")" && pwd)"
export OMARCHY_PATH="${OMARCHY_PATH:-$HOME/.local/share/omarchy}"
state="${XDG_STATE_HOME:-$HOME/.local/state}/omarchy"
step() { printf '\nhypr-omarchy: %s\n' "$1"; }

# --- 1. tools ------------------------------------------------------------------
step "checking tools"
# command:package
required=(
  start-hyprland:hyprland hyprctl:hyprland uwsm:uwsm uwsm-app:uwsm quickshell:quickshell
  hyprlock:hyprlock jq:jq socat:socat inotifywait:inotify-tools wl-copy:wl-clipboard
  grim:grim slurp:slurp gtk-launch:gtk3 xdg-terminal-exec:xdg-terminal-exec
  wezterm:wezterm busctl:systemd fc-cache:fontconfig pactl:pulseaudio-utils wpctl:wireplumber
  git:git curl:curl tar:tar
)
optional=(
  brightnessctl:brightnessctl hyprpicker:hyprpicker tesseract:tesseract udiskie:udiskie
  nautilus:nautilus wf-recorder:wf-recorder xkbcli:libxkbcommon-utils
)
missing=() missing_optional=()
for entry in "${required[@]}"; do command -v "${entry%%:*}" >/dev/null || missing+=("${entry#*:}"); done
for entry in "${optional[@]}"; do command -v "${entry%%:*}" >/dev/null || missing_optional+=("${entry#*:}"); done
[[ $(awk --version 2>/dev/null) == "GNU Awk"* ]] || missing+=(gawk) # theme templates need gawk
if command -v quickshell >/dev/null; then
  qs_version=$(quickshell --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
  if [[ -z $qs_version ]] || ! printf '0.3.1\n%s\n' "$qs_version" | sort -VC; then
    echo "quickshell ${qs_version:-unknown} is too old: the Omarchy shell needs 0.3.1 or newer"
    missing+=(quickshell)
  fi
fi
if (( ${#missing_optional[@]} )); then
  echo "optional (brightness keys, colour picker, OCR, USB automount, file manager, screen recording):"
  echo "  sudo dnf install $(printf '%s\n' "${missing_optional[@]}" | sort -u | tr '\n' ' ')"
fi
if (( ${#missing[@]} )); then
  echo "missing:"
  echo "  sudo dnf install $(printf '%s\n' "${missing[@]}" | sort -u | tr '\n' ' ')"
  echo "install those, then run 'make hypr-omarchy' again"
  exit 1
fi
echo "all required tools present"

# --- 2. Omarchy checkout ---------------------------------------------------------
step "Omarchy $OMARCHY_REF -> $OMARCHY_PATH"
if [[ ! -d $OMARCHY_PATH/.git ]]; then
  [[ -e $OMARCHY_PATH ]] && { echo "$OMARCHY_PATH exists and is not a git checkout; move it away"; exit 1; }
  git init -q "$OMARCHY_PATH"
  git -C "$OMARCHY_PATH" remote add origin "$OMARCHY_REPO"
fi
if [[ $(git -C "$OMARCHY_PATH" rev-parse -q --verify HEAD 2>/dev/null) != "$OMARCHY_REF" ]]; then
  if [[ -n $(git -C "$OMARCHY_PATH" status --porcelain 2>/dev/null) ]]; then
    echo "$OMARCHY_PATH has local changes; not switching commits"; exit 1
  fi
  git -C "$OMARCHY_PATH" fetch -q --depth 1 origin "$OMARCHY_REF"
  git -C "$OMARCHY_PATH" -c advice.detachedHead=false checkout -q "$OMARCHY_REF"
fi
echo "at $(git -C "$OMARCHY_PATH" log -1 --format='%h %cs %s')"

# --- 3. shell config ---------------------------------------------------------------
step "shell config"
if [[ -e $HOME/.config/omarchy/shell.json ]]; then
  echo "kept existing ~/.config/omarchy/shell.json"
else
  mkdir -p "$HOME/.config/omarchy"
  cp "$here/hypr-omarchy/shell.json" "$HOME/.config/omarchy/shell.json"
  echo "seeded ~/.config/omarchy/shell.json"
fi

# --- 4. terminal --------------------------------------------------------------------
terminals="$HOME/.config/hyprland-xdg-terminals.list"
if [[ ! -e $terminals ]]; then
  printf 'org.wezfurlong.wezterm.desktop\n' >"$terminals"
  echo "SUPER + RETURN opens WezTerm ($terminals)"
fi

# --- 5. theme -------------------------------------------------------------------------
step "theme"
# Our themes become Omarchy user themes (~/.config/omarchy/themes/<name>): the base theme's
# files (backgrounds, icons) plus our colours, so the theme menu can pick them later too.
for dir in "$here"/hypr-omarchy/themes/*/; do
  name=$(basename "$dir") target="$HOME/.config/omarchy/themes/$(basename "$dir")"
  if [[ ! -d $target ]]; then
    mkdir -p "$target"
    cp -r "$OMARCHY_PATH/themes/$THEME_BASE/." "$target/"
    cp -r "$dir." "$target/"
    echo "installed theme $name"
  fi
done
if [[ -e $state/current/theme/colors.toml ]]; then
  echo "kept existing theme ($(cat "$state/current/theme.name" 2>/dev/null || echo unknown))"
else
  source_dir="$HOME/.config/omarchy/themes/$THEME"
  [[ -d $source_dir ]] || source_dir="$OMARCHY_PATH/themes/$THEME"
  [[ -d $source_dir ]] || { echo "unknown theme $THEME (see $OMARCHY_PATH/themes)"; exit 1; }
  # The theme-set steps that only produce files under ~/.local/state/omarchy: copy the theme,
  # render the Hyprland/shell templates, swap it in. omarchy-theme-set itself would also
  # retheme other apps (terminals, editors, browser, herdr, Claude), so it is not used here.
  next="$state/current/next-theme"
  mkdir -p "$next"
  cp -r "$source_dir/." "$next/"
  PATH="$OMARCHY_PATH/bin:$PATH" omarchy-theme-set-templates
  mv "$next" "$state/current/theme"
  printf '%s\n' "$THEME" >"$state/current/theme.name"
  background=$(find "$state/current/theme/backgrounds" -maxdepth 1 -type f | sort | sed -n 1p)
  [[ -n $background ]] && ln -sfn "$background" "$state/current/background"
  echo "generated $THEME"
fi

# --- 6. fonts ---------------------------------------------------------------------------
step "fonts"
fonts="$HOME/.local/share/fonts"
if [[ $(fc-list : family) == *'JetBrainsMono Nerd Font'* ]]; then # no `| grep -q`: SIGPIPE + pipefail
  echo "JetBrainsMono Nerd Font present"
else
  mkdir -p "$fonts/JetBrainsMonoNerd"
  curl -fsSL "https://github.com/ryanoasis/nerd-fonts/releases/download/$NERD_FONTS_VERSION/JetBrainsMono.tar.xz" |
    tar -xJ -C "$fonts/JetBrainsMonoNerd"
  echo "installed JetBrainsMono Nerd Font $NERD_FONTS_VERSION"
fi
mkdir -p "$fonts/omarchy"
cp "$OMARCHY_PATH/default/fonts/omarchy/omarchy.ttf" "$fonts/omarchy/omarchy.ttf"
fc-cache -f "$fonts" >/dev/null

# --- 7. Strata file manager -------------------------------------------------------------
step "Strata file manager"
if [[ -x $HOME/.local/bin/strata ]]; then
  echo "kept $("$HOME/.local/bin/strata" --version 2>/dev/null || echo 'existing install') (it updates itself)"
else
  target="$(uname -m)-unknown-linux-gnu"
  archive="strata-$STRATA_VERSION-$target.tar.gz"
  url="https://github.com/lgse/strata/releases/download/v$STRATA_VERSION"
  tmp=$(mktemp -d)
  trap 'rm -r "$tmp"' EXIT
  curl -fsSL -o "$tmp/$archive" "$url/$archive"
  curl -fsSL -o "$tmp/$archive.sha256" "$url/$archive.sha256"
  (cd "$tmp" && sha256sum --check --quiet "$archive.sha256")
  if command -v gh >/dev/null && gh attestation --help >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    gh attestation verify "$tmp/$archive" --repo lgse/strata >/dev/null
    echo "checksum and GitHub build provenance verified"
  else
    echo "checksum verified (a logged-in gh with 'gh attestation' also verifies build provenance)"
  fi
  tar -xzf "$tmp/$archive" -C "$tmp"
  dir="$tmp/${archive%.tar.gz}"
  install -Dm755 "$dir/strata" "$HOME/.local/bin/strata"
  # Launcher entry + icon (the dock and app grid find it by io.github.lgse.Strata). The default
  # folder handler stays as it is, so the regular session keeps its file manager.
  install -Dm644 "$dir/io.github.lgse.Strata.svg" \
    "$HOME/.local/share/icons/hicolor/scalable/apps/io.github.lgse.Strata.svg"
  mkdir -p "$HOME/.local/share/applications"
  sed "s|^Exec=strata |Exec=$HOME/.local/bin/strata |" "$dir/io.github.lgse.Strata.desktop" \
    >"$HOME/.local/share/applications/io.github.lgse.Strata.desktop"
  update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
  echo "installed Strata $STRATA_VERSION into ~/.local/bin/strata"
fi
libs=$(ldd "$HOME/.local/bin/strata" 2>/dev/null | awk '/not found/ {print $1}' | tr '\n' ' ')
if [[ -n $libs ]]; then
  echo "Strata is missing libraries: $libs"
  echo "  sudo dnf install gtk4 gtksourceview5 poppler-glib gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good bubblewrap gvfs ffmpegthumbnailer"
fi

# --- check -----------------------------------------------------------------------------------
step "config check"
if [[ -f $HOME/.config/hypr-omarchy/hyprland.lua ]]; then
  # Hyprland aborts without XDG_RUNTIME_DIR (e.g. under sudo -u / runuser); lend it a temp one.
  runtime=${XDG_RUNTIME_DIR:-$(mktemp -d)}
  XDG_RUNTIME_DIR=$runtime Hyprland --verify-config --config "$HOME/.config/hypr-omarchy/hyprland.lua"
  [[ $runtime == "${XDG_RUNTIME_DIR:-}" ]] || rm -rf "$runtime"
else
  # shellcheck disable=SC2088 # literal ~ in a message
  echo "~/.config/hypr-omarchy is not stowed yet (make hypr-omarchy does that)"
fi
echo
echo "done. Start the session from a TTY with: hypr-omarchy"
