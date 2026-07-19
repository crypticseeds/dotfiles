#!/usr/bin/env sh
# Fresh machine bootstrap: detect OS -> install packages -> install harnesses
# -> back up conflicting defaults -> deploy with stow -> verify.
# Idempotent: safe to rerun any time.
set -eu
cd "$(dirname "$0")/.."

# 1. OS / distro detection + system packages
case "$(uname -s)" in
  Darwin)
    command -v brew >/dev/null 2>&1 || \
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    brew bundle --file packages/Brewfile
    ;;
  Linux)
    . /etc/os-release
    case "$ID" in
      ubuntu|debian)
        sudo apt-get update -qq
        grep -vE '^\s*(#|$)' packages/apt.txt | xargs sudo apt-get install -y
        ;;
      fedora)
        grep -vE '^\s*(#|$)' packages/dnf.txt | xargs sudo dnf install -y
        ;;
      *) echo "unsupported distro: $ID" >&2; exit 1 ;;
    esac
    ;;
  *) echo "unsupported OS" >&2; exit 1 ;;
esac

# 2. AI harnesses (guarded installers, skip anything already present)
sh packages/harnesses.sh

# 3. Back up conflicting distro defaults instead of failing the stow
for f in "$HOME/.zshrc" "$HOME/.bashrc"; do
  if [ -f "$f" ] && [ ! -L "$f" ]; then mv "$f" "$f.pre-dotfiles"; fi
done

# 4. Deploy + verify (make install auto-detects OS and ends with make doctor)
make install

# 5. tmux plugin manager (plugins dir is gitignored; tpm bootstraps the rest)
tpm_dir="$HOME/.config/tmux/plugins/tpm"
if [ ! -d "$tpm_dir" ]; then
  git clone --depth 1 https://github.com/tmux-plugins/tpm "$tpm_dir"
  echo "NOTE: launch tmux and press prefix + I to install tmux plugins"
fi
