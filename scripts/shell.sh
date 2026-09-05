#!/usr/bin/env sh
# Installs everything zsh/.zshrc and zsh/.config/zsh/aliases.zsh need to
# function: the prompt, plugins, and the tools behind the core aliases
# (ls -> eza, cd -> zoxide, cat -> bat, fzf, direnv, tmux). Per OS.
# Idempotent. Work tools referenced by aliases (kubectl, doppler, gt, pnpm,
# uv, ruff, docker, ...) are deliberately not installed here.
set -eu

STARSHIP_MIN=1.23 # first release with the [cpp] module used in starship.toml
BIN="$HOME/.local/bin"
mkdir -p "$BIN"
PATH="$BIN:$PATH"

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
version_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }
starship_ok() {
  have starship && version_ge "$(starship --version | sed -n '1s/^starship \([0-9.]*\).*/\1/p')" "$STARSHIP_MIN"
}

case "$(uname -s)" in
  Darwin)
    have brew || { echo "Homebrew required: https://brew.sh" >&2; exit 1; }
    say "brew: starship eza zoxide fzf bat direnv tmux zsh plugins"
    brew install starship eza zoxide fzf bat direnv tmux zsh-autosuggestions zsh-syntax-highlighting
    ;;
  Linux)
    . /etc/os-release
    case "$ID" in
      ubuntu|debian)
        say "apt: zsh eza zoxide fzf bat direnv tmux git zsh plugins"
        sudo apt-get update -qq
        sudo apt-get install -y zsh eza zoxide fzf bat direnv tmux git \
          zsh-autosuggestions zsh-syntax-highlighting
        ;;
      fedora)
        say "dnf: zsh eza zoxide fzf bat direnv tmux git zsh plugins"
        sudo dnf install -y zsh eza zoxide fzf bat direnv tmux git \
          zsh-autosuggestions zsh-syntax-highlighting
        ;;
      *) echo "unsupported distro: $ID (add it to scripts/shell.sh)" >&2; exit 1 ;;
    esac
    # Distro starship lags the config; official installer, no sudo, into ~/.local/bin
    if ! starship_ok; then
      say "starship: installing latest release to ~/.local/bin"
      curl -fsSL https://starship.rs/install.sh | sh -s -- --yes --bin-dir "$BIN"
    fi
    # Login shell -> zsh (no-op when it already is)
    zsh_path="$(command -v zsh)"
    if [ "$(getent passwd "$USER" | cut -d: -f7)" != "$zsh_path" ]; then
      say "chsh: setting login shell to $zsh_path"
      sudo chsh -s "$zsh_path" "$USER"
    fi
    ;;
  *) echo "unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac

say "versions"
for t in zsh starship eza zoxide fzf bat batcat direnv tmux git; do
  if have "$t"; then printf '  %-12s %s\n' "$t" "$("$t" --version 2>/dev/null | head -1)"; fi
done
have bat || have batcat || echo "  bat          MISSING"
for p in zsh-autosuggestions zsh-syntax-highlighting; do
  if [ -f "/usr/share/$p/$p.zsh" ] || [ -f "$(brew --prefix 2>/dev/null)/share/$p/$p.zsh" ]; then
    printf '  %-24s ok\n' "$p"
  else
    printf '  %-24s MISSING\n' "$p"
  fi
done
